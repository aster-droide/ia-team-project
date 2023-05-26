import requests
import csv
from datetime import datetime

# TODO: INDIVIDUAL PROCESSING - THREADING?

# NOTE: Change "q parameter below to change the search query


class SearchAgent:

    # SerpApi personal API key to access the endpoint
    def __init__(self):
        self.api_key = "31685c8e1078e745ff0a369a59559a99abfab59bbf708e888c0f9c4d73db207a"

    def search_scholar(self):

        # Perform search on Google Scholar using HTTP requests
        url = "https://serpapi.com/search?engine=google_scholar"  # Define the URL for the search
        params = {
            "q": "bananas",  # search query
            "engine": "google_scholar",  # this is to use the Google Scholar API engine.
            "api_key": self.api_key,  # SerpApi private key
            "num": 2    # sets number of results to return
        }  # Set the parameters for the search request
        response = requests.get(url, params=params)  # Send the GET request to the specified URL with the parameters
        search_results = response.json()  # Get the JSON response from the request
        return search_results


class DataProcessingAgent:

    @staticmethod
    def process_data(search_results):

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


class DataExportAgent:

    @staticmethod
    def export_data(processed_data, csv_file):

        # get current date and time
        time = datetime.now()

        # set file name
        file_name = time.strftime("search-export-%Y-%m-%d_%H:%M:%S")

        # set location
        location = f"/Users/astrid/PycharmProjects/ia-team-project/code/individual/astrid/csv-exports/{file_name}.csv"

        with open(location, 'w', newline='') as export_file:

            # set CSV columns
            columns = ['title', 'direct_link', 'snippet', 'type', 'publication_info', 'scholar_search_link']
            writer = csv.DictWriter(export_file, fieldnames=columns)

            # write header row
            writer.writeheader()

            # write rows to CSV
            for row in processed_data:
                writer.writerow(row)


def main():

    # search agent
    search_agent = SearchAgent()
    search_results = search_agent.search_scholar()

    # processing agents
    data_processing_agent = DataProcessingAgent()
    processed_data = data_processing_agent.process_data(search_results)

    # export data as CSV
    data_export_agent = DataExportAgent()
    data_export_agent.export_data(processed_data, "test1.s.csv")

    # print(processed_data)


if __name__ == "__main__":
    main()


