import requests
import logging
import csv
import xmltodict
import time
import queue
import os
import xml.etree.ElementTree as ET
from PyQt5.QtCore import QObject, pyqtSignal

# root logger to lowest level for debugging
logging.getLogger().setLevel(logging.DEBUG)

# custom logger
logger = logging.getLogger(__name__)

# handler log messages and set output (CLI & log file)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler('app.log')

# level of logging
console_handler.setLevel(logging.INFO)
file_handler.setLevel(logging.INFO)

# set formatting and add to handlers
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(agent)s - %(message)s')
console_handler.setFormatter(log_format)
file_handler.setFormatter(log_format)

# add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# ensure log messages will be logged
logging.getLogger().propagate = True


# create signal instance to communicate with the UI
class AgentSignals(QObject):
    no_result_arxiv = pyqtSignal(str)
    no_result_pubmed = pyqtSignal(str)
    error_arxiv = pyqtSignal(str)
    error_pubmed = pyqtSignal(str)
    error_ieee = pyqtSignal(str)
    no_result_ieee = pyqtSignal(str)
    general_error = pyqtSignal(str)
    success = pyqtSignal(str)


agent_signals = AgentSignals()


class SearchAgent:

    def __init__(self):
        self.search_running = False

    @staticmethod
    def search_arxiv(search_term, max_results):
        url = 'http://export.arxiv.org/api/query'
        params = {
            'search_query': f'all:{search_term}',
            'start': 0,
            'max_results': max_results
        }

        # set max retries for API calls in case there is an error on the API side
        max_retries = 3
        # 1second delay per try
        retry_delay = 1

        for _ in range(max_retries):
            logger.info("TRYING ARXIV", extra={"agent": "SEARCH AGENT"})

            try:
                response = requests.get(url, params=params)

                # return output with source identifier
                logger.info("arXiv response received, sending to processing queue", extra={"agent": "SEARCH AGENT"})
                return 'arXiv', response.text

            # handle generic exception since various API side errors were thrown during development
            except Exception as e:
                logger.warning(f"Request error occurred for arXiv: {str(e)}", extra={"agent": "SEARCH AGENT"})
                logger.info("Retrying arXiv...", extra={"agent": "SEARCH AGENT"})
                time.sleep(retry_delay)

        # if all retries fail, return an empty XML string so that the processing agent can deal with this
        agent_signals.error_arxiv.emit("Failed to retrieve data from arXiv API, review app.logs for more info")
        logger.error("Failed to retrieve data from arXiv API, see exception logs above", extra={"agent": "SEARCH AGENT"})
        return 'arXiv', "<?xml version='1.0' encoding='UTF-8'?><root></root>"

    @staticmethod
    def search_pubmed(search_term, max_results):
        # ESearch text searches which will return article Ids for later use in EFetch
        url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
        params = {
            'term': search_term,
            'retmax': max_results  # number of search results
        }

        # set max retries for API calls in case there is an error on the API side
        max_retries = 3
        # 1second delay per try
        retry_delay = 1

        for _ in range(max_retries):
            logger.info("TRYING PUBMED", extra={"agent": "SEARCH AGENT"})
            try:

                response = requests.get(url, params=params)
                # raise exception if non-success status code
                response.raise_for_status()

                # parse PubMed response
                root = ET.fromstring(response.content)
                # select all elements with tag name "Id"
                id_list = root.findall(".//Id")
                article_ids = [id_element.text for id_element in id_list]
                # id list as string
                id_list = ",".join(article_ids)

                logger.info("PubMed records requested Id list: %s", id_list, extra={"agent": "SEARCH AGENT"})

                if id_list:

                    try:
                        # pass the list of Ids from the above request to the EFetch API to retrieve research records,
                        # retrieved with xml for processing
                        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={id_list}&retmode=xml"
                        response = requests.get(url)
                        # raise exception if non-success status code
                        response.raise_for_status()

                        # return output with source identifier
                        logger.info("PubMed response received, sending to processing queue", extra={"agent": "SEARCH AGENT"})
                        return 'PubMed', response.text

                    # handle generic exception since various API side errors were thrown during development
                    except Exception as e:
                        logger.warning(f"Request error occurred for PubMed efetch API: {str(e)}", extra={"agent": "SEARCH AGENT"})
                        logger.info("Retrying PubMed...", extra={"agent": "SEARCH AGENT"})
                        time.sleep(retry_delay)
                        continue

                else:
                    # handling this at search level to avoid performing an unnecessary second search
                    return 'PubMed', 'No search result for this search term'

            # handle generic exception since various API side errors were thrown during development
            except Exception as e:
                logger.warning(f"Request error occurred for PubMed esearch API: {str(e)}", extra={"agent": "SEARCH AGENT"})
                logger.info("Retrying...", extra={"agent": "SEARCH AGENT"})
                time.sleep(retry_delay)
                continue

        # if all retries fail, return an empty XML string so that the processing agent can deal with this
        agent_signals.error_pubmed.emit("Failed to retrieve data from PubMed API, review app.logs for more info")
        logger.error("Failed to retrieve data from PubMed API, see exception logs above", extra={"agent": "SEARCH AGENT"})
        return 'PubMed', "<?xml version='1.0' encoding='UTF-8'?><root></root>"

    @staticmethod
    def search_ieee_xplore(search_term, num_results):
        """
        API Documentation:
        https://developer.ieee.org/docs/read/Searching_the_IEEE_Xplore_Metadata_API

        :param search_term: search query as indicated by the user
        :param num_results: max number of results to retrieve
        :return:
        """

        url = 'https://ieeexploreapi.ieee.org/api/v1/search/articles'
        api_key = 'yvfh5bf7gt543sexjv87a3cw'

        # encode the search term (mandatory as stated in IEEE Xplore API docs)
        # encoded_search_term = parse.quote(search_term)

        # Build the query parameters
        params = {
            'apikey': api_key,
            'querytext': f'title:"{search_term}" OR abstract:"{search_term}"',
            'format': 'xml',
            'max_records': num_results
        }

        # set max retries for API calls in case there is an error on the API side
        max_retries = 3
        # 1second delay per try
        retry_delay = 1

        for _ in range(max_retries):
            logger.info("TRYING IEEE XPLORE", extra={"agent": "SEARCH AGENT"})

            try:
                # requests url encodes the query params
                response = requests.get(url, params=params)
                # return output with source identifier
                logger.info("IEEE Xplore response received, sending to processing queue", extra={"agent": "SEARCH AGENT"})
                return 'IEEE Xplore', response.text

            # handle generic exception since various API side errors were thrown during development
            except Exception as e:
                logger.warning(f"Request error occurred for IEEE Xplore: {str(e)}", extra={"agent": "SEARCH AGENT"})
                logger.info("Retrying IEEE Xplore...", extra={"agent": "SEARCH AGENT"})
                time.sleep(retry_delay)
                continue

        # if all retries fail, return an empty XML string so that the processing agent can deal with this
        agent_signals.error_ieee.emit("Failed to retrieve data from IEEE Xplore API, review app.logs for more info")
        logger.error("Failed to retrieve data from IEEE Xplore API, see exception logs above", extra={"agent": "SEARCH AGENT"})
        return 'IEEE Xplore', "<?xml version='1.0' encoding='UTF-8'?><root></root>"

    def search(self, search_in_queue, processing_queue):

        self.search_running = True

        while True:

            try:

                data = search_in_queue.get(timeout=1)

                if data is None:
                    break

                search_term, max_results, arxiv, pubmed, ieee = data

                if arxiv:
                    arxiv_results = self.search_arxiv(search_term, max_results)
                    processing_queue.put((search_term, arxiv_results))

                if pubmed:
                    pubmed_results = self.search_pubmed(search_term, max_results)
                    processing_queue.put((search_term, pubmed_results))

                if ieee:
                    ieee_results = self.search_ieee_xplore(search_term, max_results)
                    processing_queue.put((search_term, ieee_results))

            except queue.Empty:
                logger.info("Search term queue is empty, waiting...", extra={"agent": "SEARCH AGENT"})
                time.sleep(5)

        # put None to indicate end of search (sentinel value)
        self.search_running = False
        processing_queue.put((None, None))


class DataProcessingAgent:

    @staticmethod
    def process_arxiv(arxiv_results, search_term):

        logger.info("Starting arXiv processing...", extra={"agent": "PROCESSING AGENT"})

        processed_data = []

        # try to parse xml data to dict and catch any errors
        try:
            dict_data = xmltodict.parse(arxiv_results)
        except Exception as e:
            agent_signals.error_arxiv.emit("Unexpected response from arXiv, review app.logs for more info")
            logger.error(f"Failed to parse XML data: {e}", extra={"agent": "PROCESSING AGENT"})
            return 'arXiv', 'unexpected response'

        # activates response log pre-processing
        # logger.info(dict_data, extra={"agent": "PROCESSING AGENT"})

        if dict_data:
            try:
                entries = dict_data['feed']['entry']
            except KeyError as e:
                # if `entry` is missing from `feed` then there are no search results
                if str(e) == "'entry'":
                    logger.warning(f"No search result for this search term for arXiv", extra={"agent": "PROCESSING AGENT"})
                    # pass message to UI
                    agent_signals.no_result_arxiv.emit("No search result for this search term for arXiv")
                    return 'arXiv', 'No search result for this search term'
                # print other KeyError
                else:
                    agent_signals.error_arxiv.emit("Unexpected response from arXiv, review app.logs for more info")
                    logger.error(f"Unexpected response from arXiv, KeyError {e}", extra={"agent": "PROCESSING AGENT"})
                    return 'arXiv', 'unexpected response'
        else:
            # this should never be hit because the search agent returns an empty xml for "processing" so
            # `dict_data` should never be empty, however putting this here just in case
            agent_signals.error_arxiv.emit("Unexpected response from arXiv, review app.logs for more info")
            logger.warning("Empty response from arXiv", extra={"agent": "PROCESSING AGENT"})
            return 'arXiv', 'unexpected response'

        # single entry is returned as dict, convert to list
        if not isinstance(entries, list):
            entries = [entries]

        # check each search result entry
        for entry in entries:

            # handle single author as dictionary to list
            authors = entry['author']
            if not isinstance(authors, list):
                authors = [authors]

            # get author name with default 'No authors listed' value if author is not present
            author_names = [author.get('name', 'No authors listed') for author in authors]

            # dictionary for each article row
            # handle each case where values might be missing
            row = {
                'Search Term': search_term,
                'Title': entry['title'] if 'title' in entry else "No title present",
                'Summary/Abstract': entry['summary'] if 'summary' in entry else "No summary present",
                'Author(s)': author_names,
                'URL': entry['id'] if 'id' in entry else "No url present"
            }

            # add row to processed data list
            processed_data.append(row)

        logger.info("arXiv processing finished", extra={"agent": "PROCESSING AGENT"})
        return 'arXiv', processed_data

    @staticmethod
    def process_pubmed(pubmed_results, search_term):

        # log if no search results presents
        if pubmed_results == 'No search result for this search term':
            logger.warning('No search result for this search term for PubMed', extra={"agent": "PROCESSING AGENT"})
            agent_signals.no_result_pubmed.emit("No search result for this search term for PubMed")
            return 'PubMed', pubmed_results

        else:

            logger.info("Starting PubMed processing...", extra={"agent": "PROCESSING AGENT"})

            processed_data = []

            # try to parse xml data to dict and catch any errors
            try:
                dict_data = xmltodict.parse(pubmed_results)
            except Exception as e:
                agent_signals.error_pubmed.emit("Unexpected response from PubMed, review app.logs for more info")
                logger.error(f"Failed to parse XML data: {e}", extra={"agent": "PROCESSING AGENT"})
                return 'PubMed', 'unexpected response'

            # Activates response log pre-processing
            # logger.info(dict_data, extra={"agent": "PROCESSING AGENT"})

            if dict_data:
                try:
                    entries = dict_data['PubmedArticleSet']['PubmedArticle']
                except KeyError as e:
                    agent_signals.error_pubmed.emit("Unexpected response from PubMed, review app.logs for more info")
                    logger.error(f"Unexpected response from pubmed KeyError: {e}. Response: {dict_data}", extra={"agent": "PROCESSING AGENT"})
                    return 'PubMed', 'unexpected response'
            else:
                logger.warning("Empty response from pubmed", extra={"agent": "PROCESSING AGENT"})
                return 'PubMed', 'unexpected response'

            # single entry is returned as dict, convert to list
            if not isinstance(entries, list):
                entries = [entries]

            # check each article entry
            for entry in entries:
                medline_citation = entry['MedlineCitation']
                article = medline_citation['Article']

                # PubMed citations may include collaborative group names, handling this case
                # also handling single/multi authors, and handling the case where LastName OR ForeName is missing
                author_names = []

                # check if there are authors (https://pubmed.ncbi.nlm.nih.gov/37369842/ for example has no
                # authors listed)
                if 'AuthorList' in article:
                    # individual author names
                    if 'Author' in article['AuthorList']:
                        authors = article['AuthorList']['Author']

                        # handle single author as dictionary to list
                        if isinstance(authors, dict):
                            authors = [authors]

                        for author in authors:
                            last_name = author.get('LastName')
                            fore_name = author.get('ForeName')

                            if last_name or fore_name:
                                full_name = ' '.join(filter(None, [last_name, fore_name]))
                                author_names.append(full_name)

                    # collective/group author
                    # checking conditions for both `CollectiveName` and `AuthorList` since an edge case might list both
                    if 'CollectiveName' in article['AuthorList']:
                        collective_name = article['AuthorList']['CollectiveName']
                        author_names.append(collective_name)

                    # if no individual or collective author names are present, set author value to "No authors listed"
                    if not author_names:
                        author_names.append("No authors listed")

                else:
                    author_names.append("No authors listed")

                # dictionary for each article row, check each entry and replace value with "No ... present" if value is missing
                row = {
                    'Search Term': search_term,
                    'Title': article['ArticleTitle'] if 'ArticleTitle' in article else "No title present",
                    'Summary/Abstract': article['Abstract']['AbstractText'] if 'Abstract' in article and 'AbstractText'
                                                                               in article['Abstract']
                    else "No abstract present",
                    'Author(s)': author_names,
                    'URL': f"https://pubmed.ncbi.nlm.nih.gov/{medline_citation['PMID']['#text']}/"  # construct URL
                }

                # add row to processed data list
                processed_data.append(row)

            logger.info("PubMed processing finished", extra={"agent": "PROCESSING AGENT"})
            return 'PubMed', processed_data

    @staticmethod
    def process_ieee_explore(ieee_results, search_term):
        logger.info("Starting IEEE Xplore processing...", extra={"agent": "PROCESSING AGENT"})

        processed_data = []

        # try to parse xml data to dict and catch any errors
        try:
            dict_data = xmltodict.parse(ieee_results)
        except Exception as e:
            agent_signals.error_ieee.emit("Unexpected response from IEEE Xplore, review app.logs for more info")
            logger.error(f"Failed to parse XML data: {e}", extra={"agent": "PROCESSING AGENT"})
            return 'IEEE Xplore', 'unexpected response'

        # activates response log pre-processing
        # logger.info(dict_data, extra={"agent": "PROCESSING AGENT"})

        if dict_data:
            try:
                articles = dict_data['articles']['article']
            except KeyError as e:
                # If `article` is missing from `articles`, then there are no search results
                if str(e) == "'article'":
                    logger.warning("No search result for this search term for IEEE Xplore",
                                   extra={"agent": "PROCESSING AGENT"})
                    # emit signal to inform UI about the no result
                    agent_signals.no_result_ieee.emit("No search result for this search term for IEEE Xplore")
                    return 'IEEE Xplore', 'No search result for this search term'
                else:
                    agent_signals.error_ieee.emit("Unexpected response from IEEE Xplore, review app.logs for more info")
                    logger.error(f"Unexpected response from IEEE Xplore, KeyError: {e}",
                                 extra={"agent": "PROCESSING AGENT"})
                    return 'IEEE Xplore', 'unexpected response'
        else:
            agent_signals.error_ieee.emit("Unexpected response from IEEE Xplore, review app.logs for more info")
            logger.warning("Empty response from IEEE Xplore", extra={"agent": "PROCESSING AGENT"})
            return 'IEEE Xplore', 'unexpected response'

        # Handle a single article as dictionary to list
        if not isinstance(articles, list):
            articles = [articles]

        # todo: DOI after all?
        # iterate through each article in the response
        for article in articles:
            author_names = []

            # handle the case if `authors` is `null` and extract author names
            if 'authors' in article and article['authors']:
                authors = article['authors'].get('author', [])
                if not isinstance(authors, list):
                    authors = [authors]
                # check list is not empty
                if authors:
                    author_names = [author['full_name'] for author in authors]
                else:
                    author_names = "No authors listed"
            else:
                author_names = "No authors listed"

            # handle the case if there is no `abstract` but there is an `abstract_url`
            if 'abstract' in article and article['abstract']:
                abstract = article['abstract']
            elif 'abstract_url' in article and article['abstract_url']:
                abstract = article['abstract_url']
            else:
                abstract = "No abstract present"

            # create a dictionary for each article row
            # handle each case where values might be missing
            row = {
                'Search Term': search_term,
                'Title': article['title'] if 'title' in article else "No title present",
                'Summary/Abstract': abstract,
                'Author(s)': author_names,
                'URL': article['html_url'] if 'html_url' in article else "No URL present"
            }

            # Add the article to the processed data list
            processed_data.append(row)

        logger.info("IEEE Xplore processing finished", extra={"agent": "PROCESSING AGENT"})
        return 'IEEE Xplore', processed_data

    def process_data(self, processing_queue, export_queue):

        # always
        while True:
            try:

                search_term, search_result_entry = processing_queue.get(timeout=1)

                # break loop if sentinel is received
                if search_result_entry is None:
                    logger.info("search_results == None, sentinel received loop will be broken", extra={"agent": "PROCESSING AGENT"})
                    break

                logger.info("search_results can be added to logs here if desired (can clog logs with large requests)", extra={"agent": "PROCESSING AGENT"})

                identifier, response_data = search_result_entry

                # Determine which API the data came from based on the identifier
                # if arxiv
                if identifier == 'arXiv':
                    logger.info("PROCESS IDENTIFIER is arXiv", extra={"agent": "PROCESSING AGENT"})
                    processed_data = self.process_arxiv(response_data, search_term)

                # elif pubmed
                elif identifier == 'PubMed':
                    logger.info("PROCESS IDENTIFIER is PubMed", extra={"agent": "PROCESSING AGENT"})
                    processed_data = self.process_pubmed(response_data, search_term)

                # elif pubmed
                elif identifier == 'IEEE Xplore':
                    logger.info("PROCESS IDENTIFIER is IEEE Xplore", extra={"agent": "PROCESSING AGENT"})
                    processed_data = self.process_ieee_explore(response_data, search_term)

                else:
                    agent_signals.general_error.emit("Unrecognised API response, review app.logs for more info")
                    logger.error("Unrecognised API response: %s", search_result_entry,
                                 extra={"agent": "PROCESSING AGENT"})
                    # go to next iteration if response not recognised
                    continue

                # Add the processed data to the output queue
                export_queue.put(processed_data)

            except queue.Empty:
                logger.info("Search result queue is empty, waiting...", extra={"agent": "PROCESSING AGENT"})
                time.sleep(1)

        # Add sentinel to output queue when finished
        export_queue.put(None)


class DataExportAgent:
    @staticmethod
    def export_data(export_queue, location):

        # Check if file exists
        file_exists = os.path.isfile(location)
        # always create CSV regardless of whether there are no results
        # this will return an empty CSV with the search term for reference
        with open(location, 'a', newline='', encoding='utf-8') as export_file:

            # set CSV columns
            columns = ['Search Term', 'Title', 'Summary/Abstract', 'Author(s)', 'URL']
            writer = csv.DictWriter(export_file, fieldnames=columns)

            # file does not exist or is empty write header row
            if not file_exists or export_file.tell() == 0:
                # header row
                writer.writeheader()

        # always
        while True:
            try:
                # get queue entry
                processed_result_entry = export_queue.get(timeout=1)

                # break loop if sentinel is received
                if processed_result_entry is None:
                    break

                # source identifier for logs
                identifier, processed_data = processed_result_entry

                # error handling
                if processed_data == 'No search result for this search term':
                    logger.info(f"No search results for {identifier}, nothing to export - continue", extra={"agent": "EXPORT AGENT"})
                    continue
                elif processed_data == 'unexpected response':
                    logger.info(f"Unexpected response for {identifier}, nothing to export - continue", extra={"agent": "EXPORT AGENT"})
                    continue
                else:
                    logger.info(f"Exporting processed {identifier} data to CSV...", extra={"agent": "EXPORT AGENT"})

                with open(location, 'a', newline='', encoding='utf-8') as export_file:
                    writer = csv.DictWriter(export_file, fieldnames=columns)

                    # write rows to CSV
                    for row in processed_data:
                        writer.writerow(row)

                    logger.info(f"Processed {identifier} data has been written to CSV at location {location}", extra={"agent": "EXPORT AGENT"})

            except queue.Empty:
                logger.info("Export queue is empty, waiting...", extra={"agent": "EXPORT AGENT"})
                time.sleep(1)

        agent_signals.success.emit("Search, process, and export agents finished - CSV will be opened")
