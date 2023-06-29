import requests
import logging
import csv
import threading
import xmltodict
import time
import queue
import os
import platform
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal

# todo: search for octopus with search nr 10 and you will get an `authorList` error for PubMed

logging.basicConfig(
    level=logging.INFO,
    filename='app.log',
    filemode='a',  # append to file created in `main_window.py`
    format='%(asctime)s - %(levelname)s - %(agent)s - %(message)s'
)

# NOTES
# todo: arxiv and pubmed provide xml only, IEEE provides json but sticking with xml for consistency and then
#  transforming locally
# todo: chosen to go for direct database link rather than DOI as DOI is not available for all results
# todo: excel has limitations - it's not recognising the encoding, there is a workaround through importing manually:
#  https://stackoverflow.com/questions/6002256/is-it-possible-to-force-excel-recognize-utf-8-csv-files-automatically/6488070#6488070
# NOTES

# todo: add stop button in UI in case one of the queues doesn't close
# todo: append to existing file seems to always append to csv numbered 9 for some reason

# create signal instance to communicate with the UI
class AgentSignals(QObject):
    no_result_arxiv = pyqtSignal(str)
    no_result_pubmed = pyqtSignal(str)
    error_arxiv = pyqtSignal(str)
    error_pubmed = pyqtSignal(str)
    general_error = pyqtSignal(str)
    success = pyqtSignal(str)


agent_signals = AgentSignals()

class SearchAgent:

    # SerpApi personal API key to access the endpoint
    def __init__(self):
        self.api_key = "31685c8e1078e745ff0a369a59559a99abfab59bbf708e888c0f9c4d73db207a"

    def api(self):
        pass

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
            logging.info("TRYING ARXIV", extra={"agent": "SEARCH AGENT"})

            try:
                response = requests.get(url, params=params)

                print(response.url)

                # return output with source identifier
                logging.info("arXiv response received as expected, sending to processing queue", extra={"agent": "SEARCH AGENT"})
                return 'arXiv', response.text

            # handle generic exception since various API side errors were thrown during development
            except Exception as e:
                logging.warning(f"Request error occurred for arXiv: {str(e)}", extra={"agent": "SEARCH AGENT"})
                logging.info("Retrying...")
                time.sleep(retry_delay)

        # if all retries fail, return an empty XML string so that the processing agent can deal with this
        agent_signals.error_arxiv.emit("Failed to retrieve data from arXiv API, review app.logs for more info")
        logging.error("Failed to retrieve data from arXiv API, see exception logs above", extra={"agent": "SEARCH AGENT"})
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
            logging.info("TRYING PUBMED", extra={"agent": "SEARCH AGENT"})
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

                logging.info("PubMed records requested Id list: %s", id_list, extra={"agent": "SEARCH AGENT"})

                if id_list:

                    try:
                        # pass the list of Ids from the above request to the EFetch API to retrieve research records,
                        # retrieved with xml for processing
                        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={id_list}&retmode=xml"
                        response = requests.get(url)
                        # raise exception if non-success status code
                        response.raise_for_status()

                        # return output with source identifier
                        logging.info("PubMed response received as expected, sending to processing queue", extra={"agent": "SEARCH AGENT"})
                        return 'PubMed', response.text

                    # handle generic exception since various API side errors were thrown during development
                    except Exception as e:
                        logging.warning(f"Request error occurred for PubMed efetch API: {str(e)}", extra={"agent": "SEARCH AGENT"})
                        logging.info("Retrying...", extra={"agent": "SEARCH AGENT"})
                        time.sleep(retry_delay)
                        continue

                else:
                    # handling this at search level to avoid performing an unnecessary second search
                    return 'PubMed', 'No search result for this search term'

            # handle generic exception since various API side errors were thrown during development
            except Exception as e:
                logging.warning(f"Request error occurred for PubMed esearch API: {str(e)}", extra={"agent": "SEARCH AGENT"})
                logging.info("Retrying...", extra={"agent": "SEARCH AGENT"})
                time.sleep(retry_delay)
                continue

        # if all retries fail, return an empty XML string so that the processing agent can deal with this
        agent_signals.error_pubmed.emit("Failed to retrieve data from PubMed API, review app.logs for more info")
        logging.error("Failed to retrieve data from PubMed API, see exception logs above", extra={"agent": "SEARCH AGENT"})
        return 'PubMed', "<?xml version='1.0' encoding='UTF-8'?><root></root>"

    def search_ieee_xplore(self, search_term):
        pass

    def search(self, processing_queue, search_term, max_results):
        print("Starting search...")
        arxiv_results = self.search_arxiv(search_term, max_results)
        processing_queue.put(arxiv_results)

        # display statement on UI
        # print("1 second pause in between search for demonstration")
        # time.sleep(1)

        print("now for the second search..")
        pubmed_results = self.search_pubmed(search_term, max_results)
        processing_queue.put(pubmed_results)

        print("search done.")
        # put None to indicate end of search (sentinel value)
        processing_queue.put(None)


class DataProcessingAgent:

    @staticmethod
    def process_arxiv(arxiv_results):

        logging.info("Starting arXiv processing...", extra={"agent": "PROCESSING AGENT"})

        processed_data = []

        dict_data = xmltodict.parse(arxiv_results)
        # print("")
        # print("")
        # print("ARXIV")
        # print(json.dumps(dict_data, indent=4))

        # activates response log pre-processing
        # logging.info(dict_data, extra={"agent": "PROCESSING AGENT"})

        if dict_data:
            try:
                entries = dict_data['feed']['entry']
            except KeyError as e:
                # if `entry` is missing from `feed` then there are no search results
                if str(e) == "'entry'":
                    logging.warning(f"No search result for this search term for arXiv", extra={"agent": "PROCESSING AGENT"})
                    # pass message to UI
                    agent_signals.no_result_arxiv.emit("No search results for this search term for arXiv")
                    return 'arXiv', 'No search result for this search term'
                # print other KeyError
                else:
                    agent_signals.error_arxiv.emit("Unexpected response from arXiv, review app.logs for more info")
                    logging.error(f"Unexpected response from arXiv, KeyError {e}", extra={"agent": "PROCESSING AGENT"})
                entries = []
        else:
            # this should never be hit because the search agent returns an empty xml for "processing" so
            # `dict_data` should never be empty, however putting this here just in case
            agent_signals.error_arxiv.emit("Unexpected response from arXiv, review app.logs for more info")
            logging.warning("Empty response from arXiv", extra={"agent": "PROCESSING AGENT"})
            entries = []

        # single entry is returned as dict, convert to list
        if not isinstance(entries, list):
            entries = [entries]

        # todo: handle encoded titles?
        # check each search result entry
        for entry in entries:

            # handle single author as dictionary to list
            authors = entry['author']
            if not isinstance(authors, list):
                authors = [authors]

            # get author name with default 'No authors listed' value if author is not present
            author_names = [author.get('name', 'No authors listed') for author in authors]

            print(author_names)

            # dictionary for each row
            # handle each case where values might be missing
            row = {
                'title': entry['title'] if 'title' in entry else "No title present",
                'summary/abstract': entry['summary'] if 'summary' in entry else "No abstract present",
                'author_names': author_names,
                'url': entry['id'] if 'id' in entry else "No url present"
            }

            # add row to processed data list
            processed_data.append(row)

        logging.info("arXiv processing finished", extra={"agent": "PROCESSING AGENT"})
        return 'arXiv', processed_data

    @staticmethod
    def process_pubmed(pubmed_results):

        # log if no search results presents
        if pubmed_results == 'No search result for this search term':
            logging.warning('No search result for this search term for PubMed', extra={"agent": "PROCESSING AGENT"})
            agent_signals.no_result_pubmed.emit("No search results for this search term for PubMed")
            return 'PubMed', pubmed_results

        else:

            logging.info("Starting PubMed processing...", extra={"agent": "PROCESSING AGENT"})

            processed_data = []

            # parse xml to dict for processing
            dict_data = xmltodict.parse(pubmed_results)
            # print("")
            # print("")
            # print("PUBMED")
            # print(json.dumps(dict_data, indent=4))

            # Activates response log pre-processing
            # logging.info(dict_data, extra={"agent": "PROCESSING AGENT"})

            if dict_data:
                try:
                    entries = dict_data['PubmedArticleSet']['PubmedArticle']
                except KeyError as e:
                    agent_signals.error_pubmed.emit("Unexpected response from PubMed, review app.logs for more info")
                    logging.error(f"Unexpected response from pubmed KeyError: {e}. Response: {dict_data}", extra={"agent": "PROCESSING AGENT"})
                    entries = []
            else:
                logging.warning("Empty response from pubmed", extra={"agent": "PROCESSING AGENT"})
                entries = []

            # single entry is returned as dict, convert to list
            if not isinstance(entries, list):
                entries = [entries]

            # check each article entry
            for entry in entries:
                medline_citation = entry['MedlineCitation']
                article = medline_citation['Article']

                print("article:", json.dumps(article, indent=4))

                # PubMed citations may include collaborative group names, handling this case
                # also handling single/multi authors, and handling the case where LastName OR ForeName is missing
                author_names = []

                # check if there are authors (https://pubmed.ncbi.nlm.nih.gov/37369842/ for example has no
                # authors listed)
                if 'AuthorList' in article:
                    # individual author names
                    if 'Author' in article['AuthorList']:
                        authors = article['AuthorList']['Author']
                        print("authors", authors)

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

                # dictionary for each row, check each entry and replace value with "No ... present" if value is missing
                row = {
                    'title': article['ArticleTitle'] if 'ArticleTitle' in article else "No title present",
                    'summary/abstract': article['Abstract']['AbstractText'] if 'Abstract' in article and 'AbstractText'
                                                                               in article['Abstract']
                    else "No abstract present",
                    'author_names': author_names,
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{medline_citation['PMID']['#text']}/"  # construct URL
                }

                # add row to processed data list
                processed_data.append(row)

            logging.info("PubMed processing finished", extra={"agent": "PROCESSING AGENT"})
            return 'PubMed', processed_data

    def process_data(self, queue_in, queue_out):

        # always
        while True:
            try:
                search_result_entry = queue_in.get(timeout=1)

                # break loop if sentinel is received
                if search_result_entry is None:
                    logging.info("search_results == None, sentinel received loop will be broken", extra={"agent": "PROCESSING AGENT"})
                    break

                logging.info("search_results can be added to logs here if desired (can clog logs with large requests)", extra={"agent": "PROCESSING AGENT"})

                # print(search_result_entry)

                identifier, response_data = search_result_entry

                # Determine which API the data came from based on the identifier
                # if arxiv
                if identifier == 'arXiv':
                    logging.info("PROCESS IDENTIFIER is arXiv", extra={"agent": "PROCESSING AGENT"})
                    processed_data = self.process_arxiv(response_data)

                # elif pubmed
                elif identifier == 'PubMed':
                    logging.info("PROCESS IDENTIFIER is PubMed", extra={"agent": "PROCESSING AGENT"})
                    processed_data = self.process_pubmed(response_data)

                else:
                    agent_signals.general_error.emit("Unrecognised API response, review app.logs for more info")
                    logging.error("Unrecognised API response: %s", search_result_entry, extra={"agent": "PROCESSING AGENT"})
                    # go to next iteration if response not recognised
                    continue

                # todo: more elif conditions here for more APIs
                # optional

                # Add the processed data to the output queue
                queue_out.put(processed_data)

            except queue.Empty:
                logging.info("Search result queue is empty, waiting...", extra={"agent": "PROCESSING AGENT"})
                time.sleep(1)

        # Add sentinel to output queue when finished
        queue_out.put(None)


class DataExportAgent:
    @staticmethod
    def export_data(queue_out, location, search_term):

        # Check if file exists
        file_exists = os.path.isfile(location)
        # always create CSV regardless of whether there are no results
        # this will return an empty CSV with the search term for reference
        with open(location, 'a', newline='', encoding='utf-8') as export_file:

            # set CSV columns
            columns = ['title', 'summary/abstract', 'author_names', 'url']
            writer = csv.DictWriter(export_file, fieldnames=columns)

            # file does not exist or is empty write header row
            if not file_exists or export_file.tell() == 0:
                # present search term at top of CSV in capitals for clarity
                # todo: add search terms here for later searches
                search_term_row = {'title': 'SEARCH TERM:', 'summary/abstract': search_term.upper()}
                writer.writerow(search_term_row)
                # empty row for clarity
                writer.writerow({})
                # header row
                writer.writeheader()

        # always
        while True:
            try:
                # get queue entry
                processed_result_entry = queue_out.get(timeout=1)

                # demonstration
                # print("5 second pause for demonstration")
                # logging.info("5 second pause in `export_data` function for demonstration")
                # time.sleep(5)

                # break loop if sentinel is received
                if processed_result_entry is None:
                    break

                # source identifier for logs
                identifier, processed_data = processed_result_entry

                if processed_data == 'No search result for this search term':
                    logging.info(f"No search results for {identifier}, no need to export data - continue", extra={"agent": "EXPORT AGENT"})
                    continue
                else:
                    logging.info(f"Exporting processed {identifier} data to CSV...", extra={"agent": "EXPORT AGENT"})

                with open(location, 'a', newline='', encoding='utf-8') as export_file:
                    writer = csv.DictWriter(export_file, fieldnames=columns)

                    # write rows to CSV
                    for row in processed_data:
                        writer.writerow(row)

                    logging.info(f"Processed {identifier} data has been written to CSV at location {location}", extra={"agent": "EXPORT AGENT"})

            except queue.Empty:
                logging.info("Export queue is empty, waiting...", extra={"agent": "EXPORT AGENT"})
                time.sleep(1)

        agent_signals.success.emit("Search, process, and export agents finished - CSV will be opened")
