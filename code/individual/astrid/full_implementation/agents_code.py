import requests
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


# todo: add assertation that a datatype is a certain datatype when extracting data, ie always a dict, list, str?
#  depending on number of entries?

# todo: arxiv and pubmed provide xml only, IEEE provides json but sticking with xml for consistency and then
#  transforming locally

# todo: chosen to go for direct database link rather than DOI as DOI is not available for all results

# todo: add stop button in UI in case one of the queues doesn't close


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
            print("TRYING ARXIV")

            try:
                response = requests.get(url, params=params)

                # return output with source identifier
                return 'arxiv', response.text

            # handle generic exception since various API side errors were thrown during development
            except Exception as e:
                print(f"Request error occurred: {str(e)}")
                print("Retrying...")
                time.sleep(retry_delay)

        # if all retries fail, return an empty XML string so that the processing agent can deal with this
        # todo: return this message to the UI
        print("Failed to retrieve data from arXiv API")
        return 'arxiv', "<?xml version='1.0' encoding='UTF-8'?><root></root>"

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
            print("TRYING PUBMED")
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

                print(id_list)

                try:

                    # pass the list of Ids from the above request to the EFetch API to retrieve research records,
                    # retrieved with xml for processing
                    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={id_list}&retmode=xml"
                    response = requests.get(url)
                    # raise exception if non-success status code
                    response.raise_for_status()

                    # return output with source identifier
                    return 'pubmed', response.text

                # handle generic exception since various API side errors were thrown during development
                except Exception as e:
                    print(f"Request error occurred: {str(e)}")
                    print("Retrying...")
                    time.sleep(retry_delay)
                    continue

            # handle generic exception since various API side errors were thrown during development
            except Exception as e:
                print(f"Request error occurred: {str(e)}")
                print("Retrying...")
                time.sleep(retry_delay)
                continue

        # if all retries fail, return an empty XML string so that the processing agent can deal with this
        # todo: return this message to the UI
        print("Failed to retrieve data from PubMed API")
        return 'pubmed', "<?xml version='1.0' encoding='UTF-8'?><root></root>"

    def search_ieee_xplore(self, search_term):
        pass

    def search(self, search_queue, search_term, max_results):
        print("Starting search...")
        arxiv_results = self.search_arxiv(search_term, max_results)
        search_queue.put(arxiv_results)

        print("1 second pause for demonstration")
        time.sleep(1)

        print("now for the second search..")
        pubmed_results = self.search_pubmed(search_term, max_results)
        search_queue.put(pubmed_results)

        print("search done.")
        # put None to indicate end of search (sentinel value)
        search_queue.put(None)


class DataProcessingAgent:

    @staticmethod
    def process_arxiv(arxiv_results):

        processed_data = []

        dict_data = xmltodict.parse(arxiv_results)
        # print("")
        # print("")
        # print("ARXIV")
        # print(json.dumps(dict_data, indent=4))

        if dict_data:
            try:
                entries = dict_data['feed']['entry']
            # todo: return this error to the UI
            except KeyError as e:
                # if `entry` is missing from `feed` then there are no search results
                if str(e) == "'entry'":
                    print(f"No search results from arXiv")
                # print other KeyError
                else:
                    print(f"Unexpected response from arXiv, KeyError {e}")
                entries = []
        else:
            # todo: return this error to the UI
            print("Empty response from arXiv")
            entries = []

        # single entry is returned as dict, convert to list
        if not isinstance(entries, list):
            entries = [entries]

        # check each search result entry
        for entry in entries:

            # handle single author as dictionary to list
            authors = entry['author']
            if not isinstance(authors, list):
                authors = [authors]

            author_names = [author['name'] for author in authors]

            # dictionary for each row
            row = {
                'title': entry['title'],
                'summary/abstract': entry['summary'],
                'author_names': author_names,
                'url': entry['id']
            }

            # add row to processed data list
            processed_data.append(row)

        return processed_data

    @staticmethod
    def process_pubmed(pubmed_results):

        processed_data = []

        # parse xml to dict for processing
        dict_data = xmltodict.parse(pubmed_results)
        # print("")
        # print("")
        # print("PUBMED")
        # print(json.dumps(dict_data, indent=4))

        if dict_data:
            try:
                entries = dict_data['PubmedArticleSet']['PubmedArticle']
            # todo: return this error to the UI
            except KeyError as e:
                print(f"Unexpected response from pubmed KeyError: {e}. Response: {dict_data}")
                entries = []
        else:
            # todo: return this error to the UI
            print("Empty response from pubmed")
            entries = []

        # single entry is returned as dict, convert to list
        if not isinstance(entries, list):
            entries = [entries]

        # check each article entry
        for entry in entries:
            medline_citation = entry['MedlineCitation']
            article = medline_citation['Article']

            # handle single author as dictionary to list
            authors = article['AuthorList']['Author']
            if not isinstance(authors, list):
                authors = [authors]

            author_names = [author['LastName'] + ' ' + author['ForeName'] for author in authors]

            # dictionary for each row
            row = {
                'title': article['ArticleTitle'],
                'summary/abstract': article['Abstract']['AbstractText'],
                'author_names': author_names,
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{medline_citation['PMID']['#text']}/"
            }

            # add row to processed data list
            processed_data.append(row)

        return processed_data

    def process_data(self, queue_in, queue_out):

        # always
        while True:
            try:
                search_results = queue_in.get(timeout=1)

                # break loop if sentinel is received
                if search_results is None:
                    print("IT IS NONE")
                    break

                print("....")
                print("....")
                print("SEARCH RESULTS: ", search_results)
                print("....")
                print("....")

                identifier, response_data = search_results

                print("SEARCH RESULTS SPLIT: ", identifier, response_data)

                # Determine which API the data came from based on the identifier
                # if arxiv
                if identifier == 'arxiv':
                    print("YES IT IS ARXIV")
                    processed_data = self.process_arxiv(response_data)
                    print("ARXIV PROCESSED:", processed_data)

                # elif pubmed
                elif identifier == 'pubmed':
                    print("YES IT IS PUBMED")
                    processed_data = self.process_pubmed(response_data)
                    print("PUBMED PROCESSED:", processed_data)

                else:
                    # todo: feed back to UI
                    print("Unrecognised response:", search_results)
                    # go to next iteration if response not recognised
                    continue

                # todo: more elif conditions here for more APIs
                # optional

                # Add the processed data to the output queue
                queue_out.put(processed_data)

            except queue.Empty:
                print("Queue is empty, waiting...")
                time.sleep(1)

        # Add sentinel to output queue when finished
        queue_out.put(None)


class DataExportAgent:
    @staticmethod
    def export_data(queue_out, location, search_term):

        # always
        while True:
            try:
                # get queue entry
                processed_data = queue_out.get(timeout=1)

                # break loop if sentinel is received
                if processed_data is None:
                    break

                # Check if file exists
                file_exists = os.path.isfile(location)

                with open(location, 'a', newline='') as export_file:

                    # todo: modify these headers appropriately (considering multiple and different API results)
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

                    # todo add exception for if processed fields not in csv columns `fieldnames`
                    # write rows to CSV
                    for row in processed_data:
                        writer.writerow(row)

            except queue.Empty:
                print("Export queue is empty, waiting...")
                time.sleep(1)


def main():
    # create event to signal termination in case of errors
    terminate_event = threading.Event()

    # create queues
    queue_in = queue.Queue()
    queue_out = queue.Queue()

    # create instances of agents
    search_agent = SearchAgent()
    data_processing_agent = DataProcessingAgent()
    data_export_agent = DataExportAgent()

    # set base file name
    file_name = "search-export"

    # Set base directory
    base_dir = "/Users/astrid/PycharmProjects/ia-team-project/code/individual/astrid/csv-exports"

    # todo: create button on UI for this, if button is clicked we will create a new file
    # Check if the user wants to create a new CSV
    new_csv = input("New CSV? True/False: ").lower() == "true"

    if new_csv:
        # Find the highest counter number for the file name
        counter = 1
        while os.path.exists(os.path.join(base_dir, f"{file_name}-{counter}.csv")):
            counter += 1

        # Append the counter to the file name
        file_name = f"{file_name}-{counter}"
    else:
        # Find the latest existing file with the base file name
        latest_file = max(
            (file for file in os.listdir(base_dir) if file.startswith(file_name) and file.endswith(".csv")),
            default=None,
        )

        # If an existing file is found, extract the counter number
        if latest_file:
            counter = int(latest_file[len(file_name) + 1:latest_file.index(".")])
            file_name = f"{file_name}-{counter}"
        else:
            # use base name if no file exists
            counter = 1
            file_name = f"{file_name}-{counter}"

    # Construct the absolute file path
    location = os.path.join(base_dir, f"{file_name}.csv")

    # get user input for search term
    search_term = input("Enter search term: ")

    # TODO: add user input for which apis to search here

    try:

        # Start the search thread
        search_thread = threading.Thread(target=search_agent.search, args=(queue_in, search_term, 2))
        search_thread.start()

        # Start the processing thread
        processing_thread = threading.Thread(target=data_processing_agent.process_data, args=(queue_in, queue_out,))
        processing_thread.start()

        # Start the export thread
        export_thread = threading.Thread(target=data_export_agent.export_data, args=(queue_out, location, search_term,))
        export_thread.start()

        # wait for all threads to finish to ensure complete data
        search_thread.join()
        processing_thread.join()
        export_thread.join()

        # Construct the absolute path to the CSV file
        csv_file_path = os.path.join('/Users/astrid/PycharmProjects/ia-team-project/code/individual/astrid/csv-exports', f'{file_name}.csv')

        # todo: if file was not created and thus doesn't exist, handle this and feed back to UI
        # open in MS Excel
        # on windows
        if platform.system() == 'Windows':
            os.system(f'start excel.exe {csv_file_path}')

        # on macOS
        elif platform.system() == 'Darwin':
            os.system(f'open {csv_file_path}')

        # linux (linux doesn't run MS Excel)
        elif platform.system() == 'Linux':
            os.system(f'xdg-open {csv_file_path}')

    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
