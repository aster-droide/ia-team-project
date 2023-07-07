# import `threading` to allow for asynchronous agent threads
# this allows the agents to work simultaneously and retrieve results quicker
import threading
# import `queue` to work with message queues for communication between agents
import queue
# import `os` to be able to check operating system's filepaths
import os
# import regular expression libray to match filenames when creating the csv
import re
# import `platform` to determine the operating system
import platform
# import `sys` to perform system operations such as opening and closing applications
import sys
# import `appdirs` to set a base directory for export location
import appdirs
# import required PyQt5 widgets for UI visualisation
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, \
    QCheckBox, QSpinBox, QScrollArea
# import the agent signals for UI info messaging and import all agents
from agents_code import agent_signals, SearchAgent, DataProcessingAgent, DataExportAgent
# import logger instance for log messages, see `logging_setup.py` for detailed comments
from logging_setup import logger

win_width, win_height = 750, 700


class MainWin(QWidget):
    """
    UI main window

    first set up message signal to signify user search query from the `handle_submit` method to the `SearchAgent`
    message is connected to the `worker` `receive_search_data` @pyqtSlot
    messages are put from the `search_button_queue` into the `search_in_queue` which is passed as an argument to
    the `SearchAgent` instance which runs on a thread
    """
    send_message = pyqtSignal(tuple)

    def __init__(self):
        super().__init__()
        # flag for the first performed search, handled in `handle_submit`
        self.first_search_performed = False
        # placeholder variable for existence of `self.worker`
        self.worker = None
        # format UI
        self.setWindowTitle("Academic Research Tool")
        self.resize(win_width, win_height)
        self.intro_label = QLabel("Welcome to the Academic Research Tool! "
                                  "<br><br>"
                                  "Please select the desired search engines,&nbsp;"
                                  "choose the maximum number of results you'd like to see per search,&nbsp;"
                                  "enter your search term then click 'Search'."
                                  "<br<br>"
                                  "When you have entered all of your search terms,&nbsp;click 'Finish' to see the "
                                  "results."
                                  "<br>")

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
        self.search_instruction_label = QLabel("<br>Enter search term:")

        # QLabel text label for search number of results instruction
        self.search_number_label = QLabel("<br>Enter desired number of results (1-50):<br>")

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
        self.submit_button = QPushButton("Search")
        # self.submit_button.clicked.connect(self.handle_submit)
        # disable button at initiation
        self.submit_button.setEnabled(False)

        # create 'Search' and 'Finish' buttons and disable them
        # self.search_button = QPushButton('Search')
        self.stop_button = QPushButton('Finish')
        # self.search_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.submit_button.clicked.connect(self.handle_submit)
        self.stop_button.clicked.connect(self.handle_stop_button)

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
        # input_layout.addWidget(self.search_button)
        input_layout.addWidget(self.stop_button)

        # QLabels for info messaging as received from the backend
        self.search_term_update = QLabel(self)
        self.search_term_update.setStyleSheet("color: blue")
        self.no_result_arxiv = QLabel(self)
        self.no_result_arxiv.setStyleSheet("color: red")
        self.no_result_pubmed = QLabel(self)
        self.no_result_pubmed.setStyleSheet("color: red")
        self.no_result_ieee = QLabel(self)
        self.no_result_ieee.setStyleSheet("color: red")
        self.error_arxiv = QLabel(self)
        self.error_arxiv.setStyleSheet("color: red")
        self.error_ieee = QLabel(self)
        self.error_ieee.setStyleSheet("color: red")
        self.error_pubmed = QLabel(self)
        self.error_pubmed.setStyleSheet("color: red")
        self.general_error = QLabel(self)
        self.general_error.setStyleSheet("color: red")
        self.stop_signal = QLabel(self)
        self.stop_signal.setStyleSheet("color: purple")
        self.success = QLabel(self)
        self.success.setStyleSheet("color: blue")
        self.finished = QLabel(self)
        self.finished.setStyleSheet("color: blue")
        self.error_message = QLabel(self)
        self.error_message.setStyleSheet("color: red")

        # create a scroll area and set the info QLabels as its widgets
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # create QWidget to hold the info QLabels
        info_widget = QWidget()
        info_layout = QVBoxLayout()
        info_layout.addWidget(self.search_term_update)
        info_layout.addWidget(self.no_result_arxiv)
        info_layout.addWidget(self.no_result_pubmed)
        info_layout.addWidget(self.no_result_ieee)
        info_layout.addWidget(self.error_arxiv)
        info_layout.addWidget(self.error_ieee)
        info_layout.addWidget(self.error_pubmed)
        info_layout.addWidget(self.general_error)
        info_layout.addWidget(self.stop_signal)
        info_layout.addWidget(self.success)
        info_layout.addWidget(self.finished)
        info_layout.addWidget(self.error_message)
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

        # handle button clicks
        self.submit_button.clicked.connect(self.enable_buttons)

        # handle agent signals
        agent_signals.no_result_arxiv.connect(self.handle_no_result_arxiv)
        agent_signals.no_result_pubmed.connect(self.handle_no_result_pubmed)
        agent_signals.no_result_ieee.connect(self.handle_no_result_ieee)
        agent_signals.error_arxiv.connect(self.handle_error_arxiv)
        agent_signals.error_ieee.connect(self.handle_error_ieee)
        agent_signals.error_pubmed.connect(self.handle_error_pubmed)
        agent_signals.general_error.connect(self.handle_general_error)
        agent_signals.success.connect(self.handle_success)

    def enable_buttons(self):
        # enable the 'Search' and 'Finish' buttons when 'Submit' button is clicked
        # self.search_button.setEnabled(True)
        self.stop_button.setEnabled(True)

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

    def handle_no_result_ieee(self, message):
        self.no_result_ieee.setText(message)
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

    def handle_error_message(self, message):
        self.error_message.setText(message)
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
        self.no_result_ieee.clear()
        self.error_arxiv.clear()
        self.error_ieee.clear()
        self.error_pubmed.clear()
        self.general_error.clear()
        self.stop_signal.clear()
        self.success.clear()
        self.finished.clear()

        # Reset the scroll area position to the top
        self.scroll_area.verticalScrollBar().setValue(0)

    def handle_submit(self):
        """
        Method that handles the user's search queries

        If the first search has not been performed yet, as set by the `self.first_search_performed` flag, we will
        establish a connection to the search query queue via
        `self.send_message.connect(self.worker.receive_search_data)` and pass the first search query to the queue

        We decided to let the user to keep giving search queries to be added to the initial CSV choice (new CSV
        or append). This was done so that the user can perform as many searches as they want in their file, different
        search terms, different max results, and different sources - should they wish to. It seemed the most user
        friendly option to us. So, if the first search is performed, we disable the CSV checkbox, change the search
        button to "Next Search", clear the search term bar, display the first search, and
        set self.first_search_performed to True so that the `else` statement will be activated for each next search.

        For each following search we will display the search term on the UI and clear appropriate checkboxes and
        input fields. Appropriate user query info will subsequently be logged to the log file, the data will be send
        to the search queue, and the UI will be updated accordingly.
        :return:
        """

        if not self.first_search_performed:

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

            logger.info("SEARCH TERM: %s", search_term, extra={"agent": "INFO"})
            logger.info("NEW CSV: %s", new_csv, extra={"agent": "INFO"})
            logger.info("NUMBER OF DESIRED SEARCH RESULTS: %s", num_results, extra={"agent": "INFO"})

            # now instantiate the worker
            self.worker = Worker(new_csv, num_results, arxiv, pubmed, ieee)
            # set up message connection for search complete
            self.worker.search_complete.connect(widget.handle_search_complete)
            # set up message connection for any errors caught in the run() method
            self.worker.run_error_messsage.connect(widget.handle_error_occured)
            # start the worker
            self.worker.start()

            # set up connection with the worker to pass user search queries to the search queues
            self.send_message.connect(self.worker.receive_search_data)

            # send first search through to search queue
            data = (search_term, num_results, arxiv, pubmed, ieee)
            self.send_message.emit(data)

            # disable the csv checkbox
            self.new_csv_checkbox.setEnabled(False)

            # set button to "Next Search" after first search
            self.submit_button.setText("Next Search")

            # Clear the QLineEdit
            self.search_term.clear()

            # make sure scroll bar is at the top
            self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().minimum())

            # show search terms on UI
            self.search_term_update.setText(f"Searching for {search_term}...")

            # set first search performed flag to True
            self.first_search_performed = True

        else:
            self.clear_info_messages()

            # check which searches are checked
            arxiv = self.checkbox_arxiv.isChecked()
            pubmed = self.checkbox_pubmed.isChecked()
            ieee = self.checkbox_ieee.isChecked()

            # get search term from the user input field
            search_term = self.search_term.text()
            num_results = self.num_results_spinbox.value()

            logger.info("SEARCH TERM: %s", search_term, extra={"agent": "INFO"})
            logger.info("NUMBER OF DESIRED SEARCH RESULTS: %s", num_results, extra={"agent": "INFO"})

            data = (search_term, num_results, arxiv, pubmed, ieee)

            self.search_term_update.setText(self.search_term_update.text() + "<br>Searching for {0}...".format(search_term))

            # Clear the QLineEdit
            self.search_term.clear()

            # send search through to search queue
            self.send_message.emit(data)

    def handle_stop_button(self):
        """
        This button is here for the user to indicate that the search is over. The button was put in place because
        otherwise the system will not know when to finalise the export (since the agents are always listening to new
        responses until a None sentinel is signalled)

        This method also signals the end to the `search_button_queue` in the worker thread, which will subsequently
        tell the SearchAgent the same so that the agents can round off their work and finish.
        :return:
        """
        # put None into the queue to stop the worker thread
        self.worker.search_button_queue.put(None)
        # set submit button back to search and grey out until the search is done
        self.submit_button.setText("Search")
        self.submit_button.setEnabled(False)
        self.stop_signal.setText("Stop signalled, finishing threads...")

        # scroll to bottom of scroll area
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def handle_search_complete(self, csv_file_path):
        """
        Since the Agent threads have been put in a separate UI Worker QThread to allow responsiveness in the UI,
        this function allows the `csv_file_path` to be communicated back to the UI so that we can present it to
        the user. It also ensures the Worker instance (self.worker) is fully shut down to avoid any issues with
        restarting the worker once the user is ready for a new search (with New CSV yes/no option). This method
        resets all the interface widgets as if the program has just been started for the first time.

        :param csv_file_path:
        :return:
        """
        # shut down Worker instance
        if self.worker is not None:
            self.worker.quit()
            self.worker.wait()
            self.worker.deleteLater()
            self.worker = None

        # notify user
        self.handle_finished("Search complete, CSV will be opened in default .csv extension application. "
                             f"<br>The file path is: {csv_file_path}")

        # enable submit button and csv checkbox again
        self.submit_button.setEnabled(True)
        self.new_csv_checkbox.setEnabled(True)

        # reset first search performed
        self.first_search_performed = False

        # set submit button back to 'Search'
        self.submit_button.setText("Search")

        # and disable stop button
        self.stop_button.setEnabled(False)

        # scroll to bottom of scroll area
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def handle_error_occured(self, worker_error_message):
        """
        This method handles any errors that could occur in the try-except blocks of the run() method in
        the Worker class. The user needs to be notified of this, this method ensures that error will be
        displayed on the UI.

        It further performs all the same actions as the `handle_search_complete` above.

        :param worker_error_message: tuple of string message and error exception to be displayed on the UI
        :return:
        """
        # shut down Worker instance
        if self.worker is not None:
            self.worker.quit()
            self.worker.wait()
            self.worker.deleteLater()
            self.worker = None

        error_message, error_caught = worker_error_message

        # notify user
        self.handle_error_message(f"{error_message} {error_caught}")

        # enable submit button and csv checkbox again
        self.submit_button.setEnabled(True)
        self.new_csv_checkbox.setEnabled(True)

        # reset first search performed
        self.first_search_performed = False

        # set submit button back to 'Search'
        self.submit_button.setText("Search")

        # and disable stop button
        self.stop_button.setEnabled(False)

        # scroll to bottom of scroll area
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())


class Worker(QThread):
    """
    The agent instantiations and instantiations of respective worker threads were causing issues with the
    responsiveness of the UI while the agents were working. We therefore decided to put this functionality
    on a separate PyQt5 QThread, to create a Worker class. This ensures the UI remains responsive, and through
    signal communication and message queues we can communicate with the different components of the system.

    At first the plan was to just run the code in the `run()` method off the `MainWin()` class, however there was
    no way for the user to signal stop to the program. This stop button was required firstly to ensure the user
    has a way to stop the search in case of any unhandled errors, but secondly to allow the user to cancel a search
    without terminating the whole program, and losing all data. It was therefore decided to put this functionality
    on a separate thread as described above.

    This allowed us to change the system in such a way that there was "true continuous agent listening". Now we were
    able to leave the search queue always open to allow the user to perform as many searches as they want.
    always listening for new queries from the user, until signalled to finish.
    """
    search_complete = pyqtSignal(str)
    run_error_messsage = pyqtSignal(tuple)

    def __init__(self, new_csv, num_results, arxiv=False, pubmed=False, ieee=False):
        super().__init__()
        self.new_csv = new_csv
        self.num_results = num_results
        self.arxiv = arxiv
        self.pubmed = pubmed
        self.ieee = ieee
        self.search_button_queue = queue.Queue()

    @pyqtSlot(tuple)
    def receive_search_data(self, data):
        self.search_button_queue.put(data)

    def run(self):

        # create queues
        search_in_queue = queue.Queue()
        processing_queue = queue.Queue()
        export_queue = queue.Queue()

        # create instances of agents
        search_agent = SearchAgent()
        data_processing_agent = DataProcessingAgent()
        data_export_agent = DataExportAgent()

        # set base file name
        file_name = "search-export"

        # set base directory
        user_data_dir = appdirs.user_data_dir(appname="IntelligentSearchAgent")
        csv_dir = os.path.join(user_data_dir, "csv-exports")
        os.makedirs(csv_dir, exist_ok=True)

        # if user signifies new CSV
        if self.new_csv:
            # find highest counter number for existing file names
            counter = 0
            while os.path.exists(os.path.join(csv_dir, f"{file_name}-{counter}.csv")):
                counter += 1

            # append counter to new file name
            file_name = f"{file_name}-{counter}"
        else:
            # find existing files with the base file name
            existing_files = [file for file in os.listdir(csv_dir) if
                              file.startswith(file_name) and file.endswith(".csv")]

            if existing_files:
                # use regex to find files matching our file_name pattern
                existing_files = [file for file in os.listdir(csv_dir) if re.match(rf"{file_name}-\d+\.csv$", file)]
                # extract counters
                existing_counters = [int(re.search(rf"{file_name}-(\d+)\.csv$", file).group(1)) for file in
                                     existing_files]
                # find highest counter and set that as `file_name` to append to
                highest_counter = max(existing_counters) if existing_counters else 0
                file_name = f"{file_name}-{highest_counter}"

            else:
                # no existing files, new file will be created
                # base name if no file exists
                counter = 0
                file_name = f"{file_name}-{counter}"

        # construct file path
        location = os.path.join(user_data_dir, "csv-exports", f"{file_name}.csv")

        try:
            # rest of code below...
            search_thread = threading.Thread(target=search_agent.search,
                                             args=(search_in_queue, processing_queue,))
            search_thread.start()

            # Start the processing thread
            processing_thread = threading.Thread(target=data_processing_agent.process_data,
                                                 args=(processing_queue, export_queue,))
            processing_thread.start()

            # Start the export thread
            export_thread = threading.Thread(target=data_export_agent.export_data,
                                             args=(export_queue, location,))
            export_thread.start()

            while True:

                data = self.search_button_queue.get()

                # Add the search term to the input queue
                search_in_queue.put(data)

                # sentinel received from `handle_stop_button` method, signal finish
                if data is None:
                    break

            # wait for all threads to finish to ensure complete data
            search_thread.join()
            processing_thread.join()
            export_thread.join()

            # open .csv with default file extension app, check for existence

            # catch any error that might occur by opening the file
            try:

                # on windows
                if platform.system() == 'Windows':
                    if os.path.exists(location):
                        os.system(f'start excel.exe "{location}"')
                    else:
                        logger.error(f"File {location} does not exist.", extra={"agent": "ERROR"})

                # on macOS
                elif platform.system() == 'Darwin':
                    if os.path.exists(location):
                        os.system(f'open "{location}"')
                    else:
                        logger.error(f"File {location} does not exist.", extra={"agent": "ERROR"})

                # linux (linux doesn't run MS Excel)
                elif platform.system() == 'Linux':
                    if os.path.exists(location):
                        os.system(f'xdg-open "{location}"')
                    else:
                        logger.error(f"File {location} does not exist.", extra={"agent": "ERROR"})

            except Exception as e:
                self.run_error_messsage.emit((str("ERROR: unable to open file: "), str(e)))
                logger.error(f"An error occurred, unable to open file: {str(e)}", extra={"agent": "ERROR"})

            self.search_complete.emit(location)

        except Exception as e:
            self.run_error_messsage.emit((str("An error occured: "), str(e)))
            logger.error(f"An error occurred: {str(e)}", extra={"agent": "ERROR"})


if __name__ == "__main__":
    app = QApplication(sys.argv)    # QApplication instance to manage the app

    widget = MainWin()  # instance of our MainWin() class
    widget.show()   # display the MainWin() instance

    sys.exit(app.exec_())   # handle app exit
