import threading
import queue
import os
import re
import platform
import sys
import logging
import multiprocessing
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QCheckBox, \
    QSpinBox, QScrollArea
from agents_code import agent_signals, SearchAgent, DataProcessingAgent, DataExportAgent

win_width, win_height = 800, 650


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

        self.worker = None

        self.setWindowTitle("Academic Research Tool")
        self.resize(win_width, win_height)

        self.intro_label = QLabel("Welcome to the Academic Research Tool! "
                                  "<br><br>"
                                  "Please select the desired search engines,&nbsp;"
                                  "choose the max number of results you'd like to see per search,&nbsp;and enter your "
                                  "search term.")

        # QLabel widget for our names
        self.names_label = QLabel("Astrid van Toor <br> Leigh Feaviour")
        self.names_label.setStyleSheet("font-size: 8px;")  # Set the font size
        self.names_label.setAlignment(Qt.AlignBottom | Qt.AlignRight)

        # create checkboxes for database search option
        self.checkbox_all = QCheckBox("Select All")
        self.checkbox_arxiv = QCheckBox("Search arXiv")
        self.checkbox_pubmed = QCheckBox("Search PubMed")
        self.checkbox_ieee = QCheckBox("Search IEEE Xplore")

        # select all checkboxes is "Select All" is checked
        self.checkbox_all.stateChanged.connect(self.handle_select_all)
        # monitor checkbox states for form validation (need a checkbox and text)
        self.checkbox_arxiv.stateChanged.connect(self.validate_form)
        self.checkbox_pubmed.stateChanged.connect(self.validate_form)
        self.checkbox_ieee.stateChanged.connect(self.validate_form)

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
        # check if form is valid to enable submit button
        self.search_term.textChanged.connect(self.validate_form)

        # QPushButton for submitting the input
        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.handle_submit)
        # set submit button to False initially
        self.submit_button.setEnabled(False)

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
        self.error_ieee = QLabel(self)
        self.error_ieee.setStyleSheet("color: red")
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
        info_layout.addWidget(self.error_ieee)
        info_layout.addWidget(self.error_pubmed)
        info_layout.addWidget(self.general_error)
        info_layout.addWidget(self.success)
        info_layout.addWidget(self.finished)
        info_widget.setLayout(info_layout)

        # create bottom layout for the scroll area and our names
        bottom_layout = QVBoxLayout()
        bottom_layout.addWidget(self.scroll_area)
        bottom_layout.addWidget(self.names_label)
        self.scroll_area.setWidget(info_widget)

        # Add layouts to the main layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(vertical_layout)
        main_layout.addLayout(input_layout)
        main_layout.addLayout(bottom_layout)

        # Set the layout for the widget
        self.setLayout(main_layout)

        # handle agent signals
        agent_signals.no_result_arxiv.connect(self.handle_no_result_arxiv)
        agent_signals.no_result_pubmed.connect(self.handle_no_result_pubmed)
        agent_signals.error_arxiv.connect(self.handle_error_arxiv)
        agent_signals.error_ieee.connect(self.handle_error_ieee)
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

    def handle_error_ieee(self, message):
        self.error_ieee.setText(message)
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

    def validate_form(self):
        # check if at least one checkbox is selected
        checkboxes_checked = self.checkbox_arxiv.isChecked() or self.checkbox_pubmed.isChecked() or \
                             self.checkbox_ieee.isChecked()

        # check if search term is not empty
        search_term_valid = bool(self.search_term.text().strip())

        # enable or disable submit button based on form validity
        self.submit_button.setEnabled(checkboxes_checked and search_term_valid)

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

        # check which searches are checked
        arxiv = self.checkbox_arxiv.isChecked()
        pubmed = self.checkbox_pubmed.isChecked()
        ieee = self.checkbox_ieee.isChecked()

        # get search term from the user input field
        search_term = self.search_term.text()
        new_csv = self.new_csv_checkbox.isChecked()
        num_results = self.num_results_spinbox.value()

        logging.info("SEARCH TERM: %s", search_term, extra={"agent": "INFO"})
        logging.info("NEW CSV: %s", new_csv, extra={"agent": "INFO"})
        logging.info("NUMBER OF DESIRED SEARCH RESULTS: %s", num_results, extra={"agent": "INFO"})

        self.worker = Worker(search_term, new_csv, num_results, arxiv, pubmed, ieee)
        self.worker.search_complete.connect(widget.handle_search_complete)
        self.worker.start()

        # Clear the QLineEdit
        self.search_term.clear()

    def handle_search_complete(self, csv_file_path):
        # self.handle_search_finished()

        if self.worker is not None:
            self.worker.quit()
            self.worker.wait()
            self.worker.deleteLater()
            self.worker = None

        self.handle_finished("Search complete, CSV has been opened in default .csv extension application. "
                             f"<br>The file path is: {csv_file_path}")


class Worker(QThread):
    search_complete = pyqtSignal(str)
    # finished = pyqtSignal()

    def __init__(self, search_term, new_csv, num_results, arxiv=False, pubmed=False, ieee=False):
        super().__init__()
        self.search_term = search_term
        self.new_csv = new_csv
        self.num_results = num_results
        self.arxiv = arxiv
        self.pubmed = pubmed
        self.ieee = ieee

    def run(self):

        # create queues
        processing_queue = queue.Queue()
        export_queue = queue.Queue()

        # create instances of agents
        search_agent = SearchAgent()
        data_processing_agent = DataProcessingAgent()
        data_export_agent = DataExportAgent()

        # set base file name
        file_name = "search-export"

        # set base directory
        base_dir = "/Users/astrid/PycharmProjects/ia-team-project/code/individual/astrid/csv-exports"

        if self.new_csv:
            # find highest counter number for existing file names
            counter = 0
            while os.path.exists(os.path.join(base_dir, f"{file_name}-{counter}.csv")):
                counter += 1

            # append counter to new file name
            file_name = f"{file_name}-{counter}"
        else:
            # find existing files with the base file name
            existing_files = [file for file in os.listdir(base_dir) if
                              file.startswith(file_name) and file.endswith(".csv")]

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

        try:

            search_thread = threading.Thread(target=search_agent.search,
                                             args=(processing_queue, self.search_term, self.num_results, self.arxiv, self.pubmed, self.ieee))
            search_thread.start()

            # Start the processing thread
            processing_thread = threading.Thread(target=data_processing_agent.process_data,
                                                 args=(processing_queue, export_queue,))
            processing_thread.start()

            # Start the export thread
            export_thread = threading.Thread(target=data_export_agent.export_data,
                                             args=(export_queue, location, self.search_term,))
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

            self.search_complete.emit(csv_file_path)

        except Exception as e:
            # todo: add UI message for this
            logging.error(f"An error occurred: {str(e)}", extra={"agent": "ERROR"})


if __name__ == "__main__":
    app = QApplication(sys.argv)

    widget = MainWin()
    widget.show()

    sys.exit(app.exec_())
