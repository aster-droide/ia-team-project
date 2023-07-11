# Intelligent Academic Research Tool 


This repository contains an Intelligent Academic Research Tool allowing users to search multiple academic 
databases simultaneously and export the search results to a CSV file. It provides a simple and convenient way 
to retrieve research articles and relevant information for a given search term. 


## Features
- Search multiple databases: arXiv, PubMed, and IEEE Xplore (for now).


- Customisable search options, users can: 
- - select the desired search engines 
- - set max number of results to retrieve 
- - retrieve results for unlimited search terms in one CSV export
- - choose a new file or append to existing file


- Data is exported to .csv format for easy access to further analysis.


- User-friendly graphical user interface (GUI) that is intuitive and easy to use.


## Installation

In [this folder](build_zips) two zip files are provided with a compiled version 
of the application for Mac* and Windows. These applications include all dependencies and can be run directly on respective platforms.

Alternatively, the application can be launched directly by running the
[academic_search_ui.py](academic_search_tool/academic_search_ui.py) file. To run locally, 
please ensure [all three Python](academic_search_tool) files are downloaded and in the same directory. 


*Unix executable compiled and tested on Mac M1, it is not guaranteed it will run as expected on intel devices or Linux. In case of failure the code can be run directly. While this has been thoroughly tested on the Mac M1 and Windows, it is not guaranteed it will work on Linux. 


## Usage

![UI Screenshot](https://github.com/aster-droide/ia-team-project/blob/6c0ed4a09e7e731eda0243a6dbb64c81bd6cafa3/screenshots/Screenshot%202023-07-11%20at%2021.18.54.png)


## Acknowledgments

This application was developed by Astrid van Toor and Leigh Feaviour as part of a team project for the MSc Intelligent 
Agents module from the University of Essex. Any questions, feel free to reach out to us. 



## Relevant sources used during development

### Tutorials and forum discussions

https://realpython.com/python-pyqt-qthread/

https://stackoverflow.com/questions/3044580/multiprocessing-vs-threading-python

https://www.pythontutorial.net/python-concurrency/python-threading/

https://stackoverflow.com/questions/27435284/multiprocessing-vs-multithreading-vs-asyncio 


### Key library documentations

https://docs.python.org/3/library/multiprocessing.html

https://docs.python.org/3/library/threading.html

https://pypi.org/project/PyQt5/
