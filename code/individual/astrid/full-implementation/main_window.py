import threading
import queue
import os
import re
import platform
import sys
import logging
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QCheckBox, \
    QSpinBox, QScrollArea
from agents_code import agent_signals, SearchAgent, DataProcessingAgent, DataExportAgent

win_width, win_height = 800, 600

# todo: add character limit

# todo: instead of adding a button to open CSV rather than opening automatically and print out path location
#  I think it's better to just open the CSV since it's unpredictable which CSV will open when something has gone wrong
#  with the search or the code, if we open the file automatically it will just be the file we're working in
#  if nothing has been written for whatever reason i don't want the program to open a file

# todo: checkboxes for APIs

# todo: add restrictions on UI level, will be easier for testing. We can assume the endpoints will have their error
#  handling in place so we don't need to deal with that. Do put an "unexpected response" message when the APIs results
#  are unexpected


# Set up logging to a file
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(agent)s - %(message)s'
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
        self.new_csv_checkbox = QCheckBox("Tick to create new CSV / leave un-ticked to append to "
                                          "existing file with highest counter (latest unless files have been deleted "
                                          "in between and their places have been filled)")

        # create a QSpinBox widget for number of search results, designed for user integer input with arrows
        # QSpinBox deals with min-max values so users are forced to select a range of 1-50
        # default value set to 10
        self.num_results_spinbox = QSpinBox()
        self.num_results_spinbox.setMinimum(1)
        self.num_results_spinbox.setMaximum(50)
        self.num_results_spinbox.setValue(10)

        # QLineEdit for user input
        self.search_term = QLineEdit()
        # set character limit of 255
        self.search_term.setMaxLength(255)

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

        # QLabels for info messaging
        self.no_result_arxiv = QLabel(self)
        self.no_result_arxiv.setStyleSheet("color: red")
        self.no_result_pubmed = QLabel(self)
        self.no_result_pubmed.setStyleSheet("color: red")
        self.error_arxiv = QLabel(self)
        self.error_arxiv.setStyleSheet("color: red")
        self.error_pubmed = QLabel(self)
        self.error_pubmed.setStyleSheet("color: red")
        self.general_error = QLabel(self)
        self.general_error.setStyleSheet("color: red")
        self.success = QLabel(self)
        self.success.setStyleSheet("color: blue")
        self.finished = QLabel(self)
        self.finished.setStyleSheet("color: blue")

        # create a scroll area and set the info QLabels as its widgets
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # create QWidget to hold the info QLabels
        info_widget = QWidget()
        info_layout = QVBoxLayout()
        info_layout.addWidget(self.no_result_arxiv)
        info_layout.addWidget(self.no_result_pubmed)
        info_layout.addWidget(self.error_arxiv)
        info_layout.addWidget(self.error_pubmed)
        info_layout.addWidget(self.general_error)
        info_layout.addWidget(self.success)
        info_layout.addWidget(self.finished)
        info_widget.setLayout(info_layout)

        # another vertical layout for info messages
        vertical_info_layout = QVBoxLayout()
        self.scroll_area.setWidget(info_widget)
        vertical_info_layout.addWidget(self.scroll_area)
        # vertical_info_layout.addWidget(self.no_result_pubmed)
        # vertical_info_layout.addWidget(self.error_arxiv)
        # vertical_info_layout.addWidget(self.error_pubmed)
        # vertical_info_layout.addWidget(self.general_error)
        # vertical_info_layout.addWidget(self.success)
        # vertical_info_layout.addWidget(self.finished)

        # Add layouts to the main layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(vertical_layout)
        main_layout.addLayout(input_layout)
        main_layout.addLayout(vertical_info_layout)

        # Set the layout for the widget
        self.setLayout(main_layout)

        self.checkbox_all.stateChanged.connect(self.handle_select_all)
        # self.checkbox_arxiv.stateChanged.connect(self.handle_checkbox_state)
        # self.checkbox_pubmed.stateChanged.connect(self.handle_checkbox_state)
        # self.checkbox_ieee.stateChanged.connect(self.handle_checkbox_state)

        # handle agent signals
        agent_signals.no_result_arxiv.connect(self.handle_no_result_arxiv)
        agent_signals.no_result_pubmed.connect(self.handle_no_result_pubmed)
        agent_signals.error_arxiv.connect(self.handle_error_arxiv)
        agent_signals.error_pubmed.connect(self.handle_error_pubmed)
        agent_signals.general_error.connect(self.handle_general_error)
        agent_signals.success.connect(self.handle_success)

    def handle_no_result_arxiv(self, message):
        self.no_result_arxiv.setText(message)
        # resize scroll area to fit message content
        self.scroll_area.updateGeometry()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def handle_no_result_pubmed(self, message):
        self.no_result_pubmed.setText(message)
        # resize scroll area to fit message content
        self.scroll_area.updateGeometry()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def handle_error_arxiv(self, message):
        self.error_arxiv.setText(message)
        # resize scroll area to fit message content
        self.scroll_area.updateGeometry()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def handle_error_pubmed(self, message):
        self.error_pubmed.setText(message)
        # resize scroll area to fit message content
        self.scroll_area.updateGeometry()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def handle_general_error(self, message):
        self.general_error.setText(message)
        # resize scroll area to fit message content
        self.scroll_area.updateGeometry()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def handle_success(self, message):
        self.success.setText(message)
        # resize scroll area to fit message content
        self.scroll_area.updateGeometry()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def handle_finished(self, message):
        self.finished.setText(message)
        # resize scroll area to fit message content
        self.scroll_area.updateGeometry()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def handle_select_all(self, state):
        # get state of "Select All" checkbox
        checked = state == Qt.Checked

        # check all if "Select All" is checked
        self.checkbox_arxiv.setChecked(checked)
        self.checkbox_pubmed.setChecked(checked)
        self.checkbox_ieee.setChecked(checked)

    def clear_info_messages(self):
        """method to clear info messages"""
        self.no_result_arxiv.clear()
        self.no_result_pubmed.clear()
        self.error_arxiv.clear()
        self.error_pubmed.clear()
        self.general_error.clear()
        self.success.clear()
        self.finished.clear()

        # Reset the scroll area position to the top
        self.scroll_area.verticalScrollBar().setValue(0)

    def handle_submit(self):
        # clear info message labels from previous search
        self.clear_info_messages()

        # get search term from the user input field
        search_term = self.search_term.text()
        new_csv = self.new_csv_checkbox.isChecked()
        num_results = self.num_results_spinbox.value()

        logging.info("SEARCH TERM: %s", search_term, extra={"agent": "INFO"})
        logging.info("NEW CSV: %s", new_csv, extra={"agent": "INFO"})
        logging.info("NUMBER OF DESIRED SEARCH RESULTS: %s", num_results, extra={"agent": "INFO"})

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

        # set base directory
        base_dir = "/Users/astrid/PycharmProjects/ia-team-project/code/individual/astrid/csv-exports"

        if new_csv:
            # find highest counter number for existing file names
            counter = 0
            while os.path.exists(os.path.join(base_dir, f"{file_name}-{counter}.csv")):
                counter += 1

            # append counter to new file name
            file_name = f"{file_name}-{counter}"
        else:
            # find existing files with the base file name
            existing_files = [file for file in os.listdir(base_dir) if file.startswith(file_name) and file.endswith(".csv")]

            if existing_files:

                # use regex to find files matching our file_name pattern
                existing_files = [file for file in os.listdir(base_dir) if re.match(rf"{file_name}-\d+\.csv$", file)]
                # extract counters
                existing_counters = [int(re.search(rf"{file_name}-(\d+)\.csv$", file).group(1)) for file in
                                     existing_files]
                # find highest counter
                highest_counter = max(existing_counters) if existing_counters else 0
                file_name = f"{file_name}-{highest_counter}"

            else:
                # base name if no file exists
                counter = 0
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

            # todo: if file was not created for whatever reason and thus doesn't exist, handle this and feed back to UI
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

            self.handle_finished("Search complete, CSV has been opened in default .csv extension application. "
                                 f"<br>The file path is: {csv_file_path}")

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}", extra={"agent": "ERROR"})


if __name__ == "__main__":
    app = QApplication(sys.argv)

    widget = MainWin()
    widget.show()

    sys.exit(app.exec_())
