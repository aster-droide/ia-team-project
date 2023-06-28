import threading
import queue
import os
import platform
import sys
import logging
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QCheckBox, \
    QSpinBox
from agents_code import SearchAgent, DataProcessingAgent, DataExportAgent

win_width, win_height = 600, 400

# todo: option for error log?
# todo: add button to open CSV rather than opening automatically and print out path location
# todo: checkboxes for APIs
# todo: label box at top, select all or clear all
# todo: add restrictions on UI level, will be easier for testing. We can assume the endpoints will have their error
#  handling in place so we don't need to deal with that. Do put an "unexpected response" message when the APIs results
#  are unexpected

# Set up logging to a file
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class MainWin(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Academic Research Tool")
        self.resize(win_width, win_height)

        self.intro_label = QLabel("Welcome to the Academic Research Tool! "
                                  "<br><br>"
                                  "Please select the desired search engines,&nbsp;"
                                  "choose the max number of results you'd like to see per search,&nbsp;and enter your "
                                  "search term.")

        # create checkboxes for database search option
        self.checkbox_all = QCheckBox("Select All")
        self.checkbox_arxiv = QCheckBox("Search arXiv")
        self.checkbox_pubmed = QCheckBox("Search PubMed")
        self.checkbox_ieee = QCheckBox("Search IEEE Xplore")

        # QLabel text label for search term
        self.search_instruction_label = QLabel("Enter search term:")

        # QLabel text label for search number of results instruction
        self.search_number_label = QLabel("Enter desired number of results (1-50):")

        # checkbox for new CSV or not
        self.new_csv_checkbox = QCheckBox("Tick to create new CSV / leave un-ticked to append to latest existing")

        # create a QSpinBox widget for number of search results, designed for user integer input with arrows
        # QSpinBox deals with min-max values so users are forced to select a range of 1-50
        # default value set to 10
        self.num_results_spinbox = QSpinBox()
        self.num_results_spinbox.setMinimum(1)
        self.num_results_spinbox.setMaximum(50)
        self.num_results_spinbox.setValue(10)

        # QLineEdit for user input
        self.search_term = QLineEdit()

        # QPushButton for submitting the input
        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.handle_submit)

        # vertical layout
        vertical_layout = QVBoxLayout()
        vertical_layout.addWidget(self.intro_label)
        vertical_layout.addWidget(self.checkbox_all)
        vertical_layout.addWidget(self.checkbox_arxiv)
        vertical_layout.addWidget(self.checkbox_pubmed)
        vertical_layout.addWidget(self.checkbox_ieee)
        vertical_layout.addWidget(self.search_number_label)
        vertical_layout.addWidget(self.num_results_spinbox)
        vertical_layout.addSpacing(20)
        vertical_layout.addWidget(self.new_csv_checkbox)
        vertical_layout.addWidget(self.search_instruction_label)

        # horizontal layout
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.search_term)
        input_layout.addWidget(self.submit_button)

        # Add layouts to the main layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(vertical_layout)
        main_layout.addLayout(input_layout)

        # Set the layout for the widget
        self.setLayout(main_layout)

        self.checkbox_all.stateChanged.connect(self.handle_select_all)
        # self.checkbox_arxiv.stateChanged.connect(self.handle_checkbox_state)
        # self.checkbox_pubmed.stateChanged.connect(self.handle_checkbox_state)
        # self.checkbox_ieee.stateChanged.connect(self.handle_checkbox_state)

    def handle_select_all(self, state):
        # get state of "Select All" checkbox
        checked = state == Qt.Checked

        # check all if "Select All" is checked
        self.checkbox_arxiv.setChecked(checked)
        self.checkbox_pubmed.setChecked(checked)
        self.checkbox_ieee.setChecked(checked)

    def handle_submit(self):
        # get search term from the user input field
        search_term = self.search_term.text()
        new_csv = self.new_csv_checkbox.isChecked()
        num_results = self.num_results_spinbox.value()

        logging.info("SEARCH TERM: %s", search_term)
        logging.info("NEW CSV: %s", new_csv)
        logging.info("NUMBER OF DESIRED SEARCH RESULTS: %s", num_results)

        # call search method
        self.search(search_term, new_csv, num_results)

        # Clear the QLineEdit
        self.search_term.clear()

    def search(self, search_term, new_csv, num_results):

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

        # TODO: add user input for which apis to search here

        try:

            # Start the search thread
            search_thread = threading.Thread(target=search_agent.search, args=(queue_in, search_term, num_results))
            search_thread.start()

            # Start the processing thread
            processing_thread = threading.Thread(target=data_processing_agent.process_data, args=(queue_in, queue_out,))
            processing_thread.start()

            # Start the export thread
            export_thread = threading.Thread(target=data_export_agent.export_data,
                                             args=(queue_out, location, search_term,))
            export_thread.start()

            # wait for all threads to finish to ensure complete data
            search_thread.join()
            processing_thread.join()
            export_thread.join()

            # Construct the absolute path to the CSV file
            csv_file_path = os.path.join(
                '/Users/astrid/PycharmProjects/ia-team-project/code/individual/astrid/csv-exports', f'{file_name}.csv')

            # todo: if file was not created and thus doesn't exist, handle this and feed back to UI
            # open with default file extension app
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
            logging.error(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    widget = MainWin()
    widget.show()

    sys.exit(app.exec_())
