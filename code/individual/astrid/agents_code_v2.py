import requests     # we will need this later
import csv
import threading
import time
import queue
import os
import platform
from datetime import datetime

# todo: delete this once done with mock data
from search_agent_mock_data import mock_1, mock_2


class SearchAgent:

    # SerpApi personal API key to access the endpoint
    def __init__(self):
        self.api_key = "31685c8e1078e745ff0a369a59559a99abfab59bbf708e888c0f9c4d73db207a"

    def search_scholar(self, search_queue, search_term):

        print("Starting search...")

        # todo: commented out for now since using mock data, but API searches will be placed here
        # Perform search on Google Scholar using HTTP requests
        # url = "https://serpapi.com/search?engine=google_scholar"  # Define the URL for the search
        # params = {
        #     "q": search_term,  # search query
        #     "engine": "google_scholar",  # this is to use the Google Scholar API engine.
        #     "api_key": self.api_key,  # SerpApi private key
        #     "num": 2    # sets number of results to return
        # }  # Set the parameters for the search request
        # response = requests.get(url, params=params)  # Send the GET request to the specified URL with the parameters
        # search_results = response.json()  # Get the JSON response from the request

        # this will be the first API call
        scholar_results = mock_1
        search_queue.put(scholar_results)

        print("5 second pause for demonstration")
        time.sleep(5)

        print("now for the second search..")
        # this will be the second API call (for e.g. arXiv)
        arxiv_results = mock_2
        search_queue.put(arxiv_results)

        print("search done.")
        # put None to indicate end of search (sentinal value)
        search_queue.put(None)


class DataProcessingAgent:

    @staticmethod
    def process_scholar(search_results):

        processed_data = []

        # go through the organic results
        for result in search_results['organic_results']:

            # dictionary for each row
            row = {
                    'title': result.get('title'),
                    'direct_link': result.get('link'),
                    'snippet': result.get('snippet'),
                    'type': result.get('type'),
                    'publication_info': result.get('publication_info', {}).get('summary'),
                    'scholar_search_link': result.get('inline_links', {}).get('versions', {}).get('link')
            }

            # add row to processed data list
            processed_data.append(row)

        return processed_data

    def process_data(self, queue_in, queue_out):

        processed_data = None

        # always
        while True:
            try:
                search_results = queue_in.get(timeout=1)

                # break loop if sentinel is received
                if search_results is None:
                    break

                # Determine which API the data came from (change later to make sure it is unique)
                if 'search_metadata' in search_results:
                    processed_data = self.process_scholar(search_results)

                # change this to a unique recogniser in the second API
                elif 'search_metadata' in search_results:
                    processed_data = self.process_scholar(search_results)

                # more elif conditions here for more APIs
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
    def export_data(queue_out, filename):

        # set location
        location = f"/Users/astrid/PycharmProjects/ia-team-project/code/individual/astrid/csv-exports/{filename}.csv"

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
                    columns = ['title', 'direct_link', 'snippet', 'type', 'publication_info', 'scholar_search_link']
                    writer = csv.DictWriter(export_file, fieldnames=columns)

                    # file does not exist or is empty write header row
                    if not file_exists or export_file.tell() == 0:
                        writer.writeheader()

                    # write rows to CSV
                    for row in processed_data:
                        writer.writerow(row)

            except queue.Empty:
                print("Export queue is empty, waiting...")
                time.sleep(1)


def main():

    # create queues
    queue_in = queue.Queue()
    queue_out = queue.Queue()

    # create instances of agents
    search_agent = SearchAgent()
    data_processing_agent = DataProcessingAgent()
    data_export_agent = DataExportAgent()

    # get current date and time & set file name
    current_time = datetime.now()
    file_name = current_time.strftime("search-export-%Y-%m-%d_%H:%M:%S")

    # Get user input for search term
    search_term = input("Enter search term: ")

    # todo: add user input for which apis to search here
    # code

    # Start the search thread
    search_thread = threading.Thread(target=search_agent.search_scholar, args=(queue_in, search_term,))
    search_thread.start()

    # Start the processing thread
    processing_thread = threading.Thread(target=data_processing_agent.process_data, args=(queue_in, queue_out))
    processing_thread.start()

    # Start the export thread
    export_thread = threading.Thread(target=data_export_agent.export_data, args=(queue_out, file_name,))
    export_thread.start()

    # wait for all threads to finish to ensure complete data
    search_thread.join()
    processing_thread.join()
    export_thread.join()

    # todo: feed back to user - show in UI or just open excel?

    # Construct the absolute path to the CSV file
    base_dir = '/Users/astrid/PycharmProjects/ia-team-project/'
    csv_file_path = os.path.join(base_dir, 'code', 'individual', 'astrid', 'csv-exports', f'{file_name}.csv')

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


if __name__ == "__main__":
    main()

