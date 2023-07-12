# import `requests` to make http requests
import requests
# import `csv` to work with .csv extension file type for search results
import csv
# import `xmltodict` to parse XML results from the research report databases into Python dictionaries
import xmltodict
# import `time` to add pauses between request retries and between message queue reporting
import time
# import `queue` to work with message queues for communication between agents
import queue
# import `os` to be able to check operating system's filepaths
import os
# import `xml.etree.ElementTree` to parse the PubMed esearch response to get a list of IDs for article retrieval
import xml.etree.ElementTree as ET
# import logger instance for log messages, see `logging_setup.py` for detailed comments
from logging_setup import logger
# import `QObject` and `pyqtSignal` to set up an `AgentSignals` class for communication messages to the UI
from PyQt5.QtCore import QObject, pyqtSignal


# build `AgentSignals` class to set up signal messages
# allows for the  communication of error messages to be displayed on the User Interface (UI)
class AgentSignals(QObject):
    no_result_arxiv = pyqtSignal(str)
    no_result_pubmed = pyqtSignal(str)
    error_arxiv = pyqtSignal(str)
    error_pubmed = pyqtSignal(str)
    error_ieee = pyqtSignal(str)
    no_result_ieee = pyqtSignal(str)
    general_error = pyqtSignal(str)
    success = pyqtSignal(str)


# create signal instance to communicate with the UI
agent_signals = AgentSignals()

"""
For both the search agent and the processing agent, document repository have individual methods for searching / 
processing. This is for a few reasons:

- the user can select any or all repositories for search results, when we know for sure that the user does not 
    want a certain repository, it is a waste of computational power to check the code as we can call separate 
    methods directly. 
- this allows for future improvements, with the current setup it is simple and straightforward to add more document 
    repository API calls should we wish to do so. 
- each document repository response requires different search url/params and processing so it makes sense to 
    have separate methods.
- The Zen of Python: 
    "There should be one-- and preferably only one --obvious way to do it" 
    and 
    "Simple is better than complex"
"""


class SearchAgent:
    """
    `SearchAgent` class to set up individual search call methods
    and a general `search` method acting as our 'listener'

    Currently, searches are performed in sequence - and not parallel. The search agent picks up entries from
    the message queue one by one and performs the search to the relevant repository. Considering the network
    requests are  very quick at the current scale, it seemed unnecessary to put these methods on separate threads
    for parallel processing. However, if we were to scale in the future this can be improved with asynchronous
    solutions.
    """

    @staticmethod
    def search_arxiv(search_term, max_results):
        """
        `search_arxiv` is self-contained and does not rely on the instance of this class (staticmethod)
        
        API Documentation:
        https://info.arxiv.org/help/api/basics.html

        :param search_term: search query as provided by the user
        :param max_results: max number of results to retrieve
        :return: search result for the `processing_queue`
        """

        # build url
        url = 'http://export.arxiv.org/api/query'
        params = {
            'search_query': f'all:{search_term}',  # search query
            'start': 0,     # define index of first returned as 0 to ensure we get top results
            'max_results': max_results  # max number of search results
        }

        # set max retries for API calls in case there is an error on the API side
        max_retries = 3
        # 1second delay per try
        retry_delay = 1

        # loop over `max_retries`
        for _ in range(max_retries):
            # log message
            logger.info("TRYING ARXIV", extra={"agent": "SEARCH AGENT"})

            # try to make the request
            try:
                response = requests.get(url, params=params)
                # log message
                logger.info("arXiv response received, sending to processing queue", extra={"agent": "SEARCH AGENT"})
                # return output with source identifier
                return 'arXiv', response.text

            # handle generic exception since various API side errors were thrown during development
            except Exception as e:
                # log messages
                logger.warning(f"Request error occurred for arXiv: {str(e)}", extra={"agent": "SEARCH AGENT"})
                logger.info("Retrying arXiv...", extra={"agent": "SEARCH AGENT"})
                # allow 1 second time before retrying
                time.sleep(retry_delay)
                # continue with loop
                continue

        # if all retries fail, return an empty XML string so that the processing agent can handle this
        # send appropriate signal info message to UI
        agent_signals.error_arxiv.emit("Failed to retrieve data from arXiv API, review app.logs for more info")
        # log message
        logger.error("Failed to retrieve data from arXiv API, see exception logs above", extra={"agent": "SEARCH AGENT"})
        return 'arXiv', "<?xml version='1.0' encoding='UTF-8'?><root></root>"

    @staticmethod
    def search_pubmed(search_term, max_results):
        """
        `search_pubmed` is self-contained and does not rely on the instance of this class (staticmethod)
        
        API Documentation:
        https://www.ncbi.nlm.nih.gov/books/NBK25501/

        To get the desired results from PubMed, we are required to make 2 API calls
        1st for the ID list of articles matching our query through the ESearch API
        2nd to fetch the actual articles through the EFetch API

        :param search_term: search query as provided by the user
        :param max_results: max number of results to retrieve
        :return: search result for the `processing_queue`
        """
        # ESearch text searches which will return article Ids for later use in EFetch
        url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
        params = {
            'term': search_term,  # search query
            'retmax': max_results  # max number of search results
        }

        # set max retries for API calls in case there is an error on the API side
        max_retries = 3
        # 1second delay per try
        retry_delay = 1

        # loop over `max_retries`
        for _ in range(max_retries):
            logger.info("TRYING PUBMED", extra={"agent": "SEARCH AGENT"})
            # try to make the ESearch request
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

                # log message
                logger.info("PubMed records requested Id list: %s", id_list, extra={"agent": "SEARCH AGENT"})

                # if we got the article Ids, perform EFetch request to fetch the articles
                if id_list:

                    # try to make the EFetch request
                    try:
                        # pass the list of Ids from the above request to the EFetch API to retrieve research records,
                        # retrieved with xml for processing
                        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={id_list}&retmode=xml"
                        response = requests.get(url)
                        # raise exception if non-success status code
                        response.raise_for_status()

                        # log message
                        logger.info("PubMed response received, sending to processing queue", extra={"agent": "SEARCH AGENT"})
                        # return output with source identifier
                        return 'PubMed', response.text

                    # handle generic exception since various API side errors were thrown during development
                    except Exception as e:
                        # log messages
                        logger.warning(f"Request error occurred for PubMed efetch API: {str(e)}", extra={"agent": "SEARCH AGENT"})
                        logger.info("Retrying PubMed...", extra={"agent": "SEARCH AGENT"})
                        # allow 1 second time before retrying
                        time.sleep(retry_delay)
                        # continue with loop
                        continue

                else:
                    # handling this at search level to avoid performing an unnecessary second search
                    return 'PubMed', 'No search result for this search term'

            # handle generic exception since various API side errors were thrown during development
            except Exception as e:
                # log messages
                logger.warning(f"Request error occurred for PubMed esearch API: {str(e)}", extra={"agent": "SEARCH AGENT"})
                logger.info("Retrying...", extra={"agent": "SEARCH AGENT"})
                # allow 1 second time before retrying
                time.sleep(retry_delay)
                # continue with loop
                continue

        # if all retries fail, return an empty XML string so that the processing agent can handle this
        # send appropriate signal info message to UI
        agent_signals.error_pubmed.emit("Failed to retrieve data from PubMed API, review app.logs for more info")
        # log message
        logger.error("Failed to retrieve data from PubMed API, see exception logs above", extra={"agent": "SEARCH AGENT"})
        return 'PubMed', "<?xml version='1.0' encoding='UTF-8'?><root></root>"

    @staticmethod
    def search_ieee_xplore(search_term, num_results):
        """
        `search_ieee_xplore` is self-contained and does not rely on the instance of this class (staticmethod)
        
        API Documentation:
        https://developer.ieee.org/docs/read/Searching_the_IEEE_Xplore_Metadata_API

        :param search_term: search query as provided by the user
        :param num_results: max number of results to retrieve
        :return: search result for the `processing_queue`
        """

        # set url
        url = 'https://ieeexploreapi.ieee.org/api/v1/search/articles'
        # our personal API key (required)
        api_key = 'yvfh5bf7gt543sexjv87a3cw'

        # Build the query parameters
        params = {
            'apikey': api_key,  # our personal API key
            'querytext': f'title:"{search_term}" OR abstract:"{search_term}"',  # search both title and abstract for
            # our query, the other methods search these two by default
            'format': 'xml',    # set format to `xml` for consistency with other methods
            'max_records': num_results  # max number of search results
        }

        # set max retries for API calls in case there is an error on the API side
        max_retries = 3
        # 1second delay per try
        retry_delay = 1

        # loop over `max_retries`
        for _ in range(max_retries):
            # log message
            logger.info("TRYING IEEE XPLORE", extra={"agent": "SEARCH AGENT"})

            # try to make the request
            try:
                # requests url encodes the query params
                response = requests.get(url, params=params)
                # log message
                logger.info("IEEE Xplore response received, sending to processing queue", extra={"agent": "SEARCH AGENT"})
                # return output with source identifier
                return 'IEEE Xplore', response.text

            # handle generic exception since various API side errors were thrown during development
            except Exception as e:
                # log messages
                logger.warning(f"Request error occurred for IEEE Xplore: {str(e)}", extra={"agent": "SEARCH AGENT"})
                logger.info("Retrying IEEE Xplore...", extra={"agent": "SEARCH AGENT"})
                # allow 1 second time before retrying
                time.sleep(retry_delay)
                continue

        # if all retries fail, return an empty XML string so that the processing agent can handle this
        # send appropriate signal info message to UI
        agent_signals.error_ieee.emit("Failed to retrieve data from IEEE Xplore API, review app.logs for more info")
        # log message
        logger.error("Failed to retrieve data from IEEE Xplore API, see exception logs above", extra={"agent": "SEARCH AGENT"})
        return 'IEEE Xplore', "<?xml version='1.0' encoding='UTF-8'?><root></root>"

    def search(self, search_in_queue, processing_queue):
        """
        Takes two queue.Queue() objects:

        :param search_in_queue: to listen for queue entries of any user provided search queries
        :param processing_queue: for the response results from the `search_in_queue` entry queries
        to pass to the processing agent
        :return: n/a
        """

        # always until sentinel value (None) is passed to `search_in_queue`
        while True:

            # always check for entries in the `search_in_queue` with 1 second pause
            try:
                # try to get queue entry
                data = search_in_queue.get(timeout=1)

                # if queue entry is None, break loop
                # sentinel value has been passed to signal the end of the user's search queries
                if data is None:
                    break

                # unpack `data` tuple for argument use in search repo method calls
                # arxiv, pubmed, ieee are boolean values to signify search or not
                search_term, max_results, arxiv, pubmed, ieee = data

                # search appropriate databases and put results in `processing_queue`

                if arxiv:
                    arxiv_results = self.search_arxiv(search_term, max_results)
                    processing_queue.put((search_term, arxiv_results))

                if pubmed:
                    pubmed_results = self.search_pubmed(search_term, max_results)
                    processing_queue.put((search_term, pubmed_results))

                if ieee:
                    ieee_results = self.search_ieee_xplore(search_term, max_results)
                    processing_queue.put((search_term, ieee_results))

            # log message if queue is empty and wait 1 second
            except queue.Empty:
                logger.info("Search term queue is empty, waiting...", extra={"agent": "SEARCH AGENT"})
                time.sleep(1)

        # put None to indicate end of search (sentinel value)
        processing_queue.put((None, None))


class DataProcessingAgent:
    """
    `DataProcessingAgent` to process individual search results
    and a general `process_data` method acting as our 'listener'
    """

    @staticmethod
    def process_arxiv(arxiv_results, search_term):
        """
        `process_arxiv` is self-contained and does not rely on the instance of this class (staticmethod)
        
        Process arXiv search results:
        
        :param arxiv_results: arXiv search results for processing
        :param search_term: user's search term to append to article dictionary row
        :return: 
        """
        # log message
        logger.info("Starting arXiv processing...", extra={"agent": "PROCESSING AGENT"})

        # placeholder variable for `processed_data` to ensure variable existence
        processed_data = []

        # try to parse xml data to dict and catch any errors
        try:
            dict_data = xmltodict.parse(arxiv_results)
        except Exception as e:
            # send appropriate signal info message to UI
            agent_signals.error_arxiv.emit("Unexpected response from arXiv, review app.logs for more info")
            # log message
            logger.error(f"Failed to parse XML data: {e}", extra={"agent": "PROCESSING AGENT"})
            return 'arXiv', 'unexpected response'

        # uncommented for response debugging
        # import json
        # print(json.dumps(dict_data, indent=4))

        # uncomment to activate response log pre-processed
        # logger.info(dict_data, extra={"agent": "PROCESSING AGENT"})

        # perform processing
        if dict_data:
            try:
                # try and assign the search result entries
                entries = dict_data['feed']['entry']
            except KeyError as e:
                # if `entry` is missing from `feed` then there are no search results
                if str(e) == "'entry'":
                    # log message
                    logger.warning(f"No search result for this search term for arXiv", extra={"agent": "PROCESSING AGENT"})
                    # emit signal to inform UI about the no result
                    agent_signals.no_result_arxiv.emit("No search result for this search term for arXiv")
                    return 'arXiv', 'No search result for this search term'
                # any other KeyError
                else:
                    # emit signal to inform UI about the error
                    agent_signals.error_arxiv.emit("Unexpected response from arXiv, review app.logs for more info")
                    # log message
                    logger.error(f"Unexpected response from arXiv, KeyError {e}", extra={"agent": "PROCESSING AGENT"})
                    return 'arXiv', 'unexpected response'
        else:
            # this should never be hit because the search agent returns an empty xml for "processing" so
            # `dict_data` should never be empty, however putting this here just in case
            # send appropriate signal info message to UI
            agent_signals.error_arxiv.emit("Unexpected response from arXiv, review app.logs for more info")
            # log message
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

        # log message and return processed results 
        logger.info("arXiv processing finished", extra={"agent": "PROCESSING AGENT"})
        return 'arXiv', processed_data

    @staticmethod
    def process_pubmed(pubmed_results, search_term):
        """
        `process_pubmed` is self-contained and does not rely on the instance of this class (staticmethod)
        
        Process PubMed search results:
        
        :param pubmed_results: PubMed search results for processing
        :param search_term: user's search term to append to article dictionary row
        :return: 
        """

        # log if no search results presents
        if pubmed_results == 'No search result for this search term':
            # log message
            logger.warning('No search result for this search term for PubMed', extra={"agent": "PROCESSING AGENT"})
            # send appropriate signal info message to UI
            agent_signals.no_result_pubmed.emit("No search result for this search term for PubMed")
            return 'PubMed', pubmed_results

        else:
            # log message
            logger.info("Starting PubMed processing...", extra={"agent": "PROCESSING AGENT"})

            # placeholder variable for `processed_data` to ensure variable existence
            processed_data = []

            # try to parse xml data to dict and catch any errors
            try:
                dict_data = xmltodict.parse(pubmed_results)
            except Exception as e:
                # send appropriate signal info message to UI
                agent_signals.error_pubmed.emit("Unexpected response from PubMed, review app.logs for more info")
                # log message
                logger.error(f"Failed to parse XML data: {e}", extra={"agent": "PROCESSING AGENT"})
                return 'PubMed', 'unexpected response'

            # uncomment to activate response log pre-processed
            # logger.info(dict_data, extra={"agent": "PROCESSING AGENT"})

            # uncomment to activate response log pre-processed
            # logger.info(dict_data, extra={"agent": "PROCESSING AGENT"})

            # perform processing
            if dict_data:
                try:
                    entries = dict_data['PubmedArticleSet']['PubmedArticle']
                except KeyError as e:
                    # response not as expected
                    # send appropriate signal info message to UI
                    agent_signals.error_pubmed.emit("Unexpected response from PubMed, review app.logs for more info")
                    # log message
                    logger.error(f"Unexpected response from pubmed KeyError: {e}. Response: {dict_data}", extra={"agent": "PROCESSING AGENT"})
                    return 'PubMed', 'unexpected response'
            else:
                # this should never be hit because the search agent returns an empty xml for "processing" so
                # `dict_data` should never be empty, however putting this here just in case
                # send appropriate signal info message to UI
                agent_signals.error_pubmed.emit("Unexpected response from PubMed, review app.logs for more info")
                # log message
                logger.warning("Empty response from pubmed", extra={"agent": "PROCESSING AGENT"})
                return 'PubMed', 'unexpected response'

            # uncommented for response debugging
            # import json
            # print(json.dumps(dict_data, indent=4))

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
                # else there are no authors listed in the article
                else:
                    author_names.append("No authors listed")

                # dictionary for each article row, check each entry and replace value 
                # with "No ... present" if value is missing
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

            # log message and return processed results 
            logger.info("PubMed processing finished", extra={"agent": "PROCESSING AGENT"})
            return 'PubMed', processed_data

    @staticmethod
    def process_ieee_xplore(ieee_results, search_term):
        """
        `process_ieee_xplore` is self-contained and does not rely on the instance of this class (staticmethod)
        
        Process IEEE Xplore search results:
        
        :param ieee_results: PubMed search results for processing
        :param search_term: user's search term to append to article dictionary row
        :return: 
        """
        # log message
        logger.info("Starting IEEE Xplore processing...", extra={"agent": "PROCESSING AGENT"})

        # placeholder variable for `processed_data` to ensure variable existence
        processed_data = []

        # try to parse xml data to dict and catch any errors
        try:
            dict_data = xmltodict.parse(ieee_results)
        except Exception as e:
            # send appropriate signal info message to UI
            agent_signals.error_ieee.emit("Unexpected response from IEEE Xplore, review app.logs for more info")
            # log message
            logger.error(f"Failed to parse XML data: {e}", extra={"agent": "PROCESSING AGENT"})
            return 'IEEE Xplore', 'unexpected response'

        # uncommented for response debugging
        # import json
        # print(json.dumps(dict_data, indent=4))

        # uncomment to activate response log pre-processed
        # logger.info(dict_data, extra={"agent": "PROCESSING AGENT"})

        # perform processing
        if dict_data:
            try:
                articles = dict_data['articles']['article']
            except KeyError as e:
                # If `article` is missing from `articles`, then there are no search results
                if str(e) == "'article'":
                    # log message
                    logger.warning("No search result for this search term for IEEE Xplore",
                                   extra={"agent": "PROCESSING AGENT"})
                    # emit signal to inform UI about the no result
                    agent_signals.no_result_ieee.emit("No search result for this search term for IEEE Xplore")
                    return 'IEEE Xplore', 'No search result for this search term'
                # any other KeyError
                else:
                    # emit signal to inform UI about the error
                    agent_signals.error_ieee.emit("Unexpected response from IEEE Xplore, review app.logs for more info")
                    # log message
                    logger.error(f"Unexpected response from IEEE Xplore, KeyError: {e}",
                                 extra={"agent": "PROCESSING AGENT"})
                    return 'IEEE Xplore', 'unexpected response'
        else:
            # this should never be hit because the search agent returns an empty xml for "processing" so
            # `dict_data` should never be empty, however putting this here just in case
            # send appropriate signal info message to UI
            agent_signals.error_ieee.emit("Unexpected response from IEEE Xplore, review app.logs for more info")
            # log message
            logger.warning("Empty response from IEEE Xplore", extra={"agent": "PROCESSING AGENT"})
            return 'IEEE Xplore', 'unexpected response'

        # Handle a single article as dictionary to list
        if not isinstance(articles, list):
            articles = [articles]

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

        # log message and return processed results 
        logger.info("IEEE Xplore processing finished", extra={"agent": "PROCESSING AGENT"})
        return 'IEEE Xplore', processed_data

    def process_data(self, processing_queue, export_queue):
        """
        Takes two queue.Queue() objects:

        :param processing_queue: to listen for queue entries for any search results to process
        :param export_queue: to pass the processed data as as queue entries to the export agent
        :return:
        """

        # always until sentinel value (None) is passed to `search_in_queue`
        while True:
            # always check for entries in the `processing_queue` with 1 second pause
            try:
                search_term, search_result_entry = processing_queue.get(timeout=1)

                # if queue entry is None, break loop
                # sentinel value has been passed to signal the end of the user's search queries
                if search_result_entry is None:
                    # log message
                    logger.info("search_results == None, sentinel received loop will be broken",
                                extra={"agent": "PROCESSING AGENT"})
                    break

                # log message
                logger.info("search_results can be added to logs here if desired (can clog logs with large requests)",
                            extra={"agent": "PROCESSING AGENT"})

                # unpack tuple to identify source and send response data to the appropriate processing method
                identifier, response_data = search_result_entry

                # Determine which API the data came from based on the identifier
                # if arxiv
                if identifier == 'arXiv':
                    # log message
                    logger.info("PROCESS IDENTIFIER is arXiv", extra={"agent": "PROCESSING AGENT"})
                    # process data
                    processed_data = self.process_arxiv(response_data, search_term)

                # elif pubmed
                elif identifier == 'PubMed':
                    # log message
                    logger.info("PROCESS IDENTIFIER is PubMed", extra={"agent": "PROCESSING AGENT"})
                    # log message
                    processed_data = self.process_pubmed(response_data, search_term)

                # elif ieee
                elif identifier == 'IEEE Xplore':
                    # log message
                    logger.info("PROCESS IDENTIFIER is IEEE Xplore", extra={"agent": "PROCESSING AGENT"})
                    # process data
                    processed_data = self.process_ieee_xplore(response_data, search_term)

                else:
                    # notify UI with appropriate message
                    agent_signals.general_error.emit("Unrecognised API response, review app.logs for more info")
                    # log message
                    logger.error("Unrecognised API response: %s", search_result_entry,
                                 extra={"agent": "PROCESSING AGENT"})
                    # go to next iteration if response not recognised
                    continue

                # Add the processed data to the output queue
                export_queue.put(processed_data)

            # log message if queue is empty and wait 1 second
            except queue.Empty:
                logger.info("Search result queue is empty, waiting...", extra={"agent": "PROCESSING AGENT"})
                time.sleep(1)

        # put None to indicate end of search (sentinel value)
        export_queue.put(None)


class DataExportAgent:
    """
    `DataExportAgent` with a single method to export the data in an appropriate format
    data is received from the processing agent by listening to constant messages
    CSV format was chosen since it is a good format to work with in Python for further processing and
    because it allows the user to easily view the data in their default application associated with .csv
    """

    def export_data(self, export_queue, location):
        """
        Takes one queue.Queue() object and a file location

        :param export_queue: to listen for queue entries for any processed data ready to be appended to the CSV export
        :param location: the location of the CSV file to append to
        :return:
        """

        # Check if file exists
        file_exists = os.path.isfile(location)
        # always create CSV regardless of whether there are no results
        # this will return an empty CSV with the search term for reference
        # this was chosen for consistency and to know what to expect for error handling
        # the UI will update messages accordingly
        with open(location, 'a', newline='', encoding='utf-8') as export_file:

            # set CSV columns
            columns = ['Search Term', 'Title', 'Summary/Abstract', 'Author(s)', 'URL']
            writer = csv.DictWriter(export_file, fieldnames=columns)

            # file does not exist or is empty write header row
            if not file_exists or export_file.tell() == 0:
                # header row
                writer.writeheader()

        # always until sentinel value (None) is passed to `export_queue`
        while True:
            try:
                # try to get queue entry
                processed_result_entry = export_queue.get(timeout=1)

                # if queue entry is None, break loop
                # sentinel value has been passed to signal the end of the user's search queries
                if processed_result_entry is None:
                    break

                # unpack tuple to identify source and append processed data to csv
                identifier, processed_data = processed_result_entry

                # error handling and log appropriate messages
                if processed_data == 'No search result for this search term':
                    logger.info(f"No search results for {identifier}, nothing to export - continue",
                                extra={"agent": "EXPORT AGENT"})
                    continue
                elif processed_data == 'unexpected response':
                    logger.info(f"Unexpected response for {identifier}, nothing to export - continue",
                                extra={"agent": "EXPORT AGENT"})
                    continue
                else:
                    logger.info(f"Exporting processed {identifier} data to CSV...", extra={"agent": "EXPORT AGENT"})

                # open csv file for appending
                with open(location, 'a', newline='', encoding='utf-8') as export_file:
                    writer = csv.DictWriter(export_file, fieldnames=columns)

                    # write rows to CSV
                    for row in processed_data:
                        writer.writerow(row)

                    # log message
                    logger.info(f"Processed {identifier} data has been written to CSV at location {location}",
                                extra={"agent": "EXPORT AGENT"})

            # log message if queue is empty and wait 1 second
            except queue.Empty:
                logger.info("Export queue is empty, waiting...", extra={"agent": "EXPORT AGENT"})
                time.sleep(1)

        # search concluded, signify UI
        agent_signals.success.emit("Search, process, and export agents finished - CSV will be opened")
