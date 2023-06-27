import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QCheckBox

win_width, win_height = 600, 400


# todo: add button to open CSV rather than opening automatically and print out path location
# todo: checkboxes for APIs
# todo: label box at top, select all or clear all
# todo: add restrictions on UI level, will be easier for testing. We can assume the endpoints will have their error
#  handling in place so we don't need to deal with that. Do put an "unexpected response" message when the APIs results
#  are unexpected

class MainWin(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Academic Research Tool")
        self.resize(win_width, win_height)

        self.intro_label = QLabel("Welcome to the Academic Research Tool!")

        # create checkboxes for database search option
        self.checkbox_all = QCheckBox("Select All")
        self.checkbox_arxiv = QCheckBox("Search arXiv")
        self.checkbox_pubmed = QCheckBox("Search PubMed")
        self.checkbox_ieee = QCheckBox("Search IEEE Xplore")

        # QLabel text label
        self.instruction_label = QLabel("Enter search term:")

        # QLineEdit for user input
        self.search_line_edit = QLineEdit()

        # QPushButton for submitting the input
        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.handle_submit)

        # vertical layout
        vertical_layout = QVBoxLayout()
        vertical_layout.addWidget(self.checkbox_all)
        vertical_layout.addWidget(self.checkbox_arxiv)
        vertical_layout.addWidget(self.checkbox_pubmed)
        vertical_layout.addWidget(self.checkbox_ieee)
        vertical_layout.addWidget(self.intro_label)
        vertical_layout.addWidget(self.instruction_label)
        vertical_layout.setSpacing(0)

        # horizontal layout
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.search_line_edit)
        input_layout.addWidget(self.submit_button)

        # Add layouts to the main layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(vertical_layout)
        main_layout.addLayout(input_layout)

        # Set the layout for the widget
        self.setLayout(main_layout)

        # self.checkbox_all.stateChanged.connect(self.handle_select_all)
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
        # Get the user input from the QLineEdit
        search_term = self.search_line_edit.text()
        print("Search term:", search_term)
        # Do something with the search term here

        # Clear the QLineEdit
        self.search_line_edit.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    widget = MainWin()
    widget.show()

    sys.exit(app.exec_())
