# AI Web Scraper Pro

Welcome to **AI Web Scraper Pro** – an all-in-one solution for scraping web data and managing it through a friendly GUI. This tool integrates several components to help you:

- Scrape data from websites with Python.
- Use advanced search features and filters.
- Export results in CSV or JSON formats.
- View logs and error messages with detailed debugging information.
- Automatically create and update your SQLite database with scraped data.

## Features

- **Graphical User Interface:**  
  The GUI (implemented in [gui.py](gui.py)) lets you start scraping, view and filter results, export data, and debug errors—all without writing a single line of code.

- **Data Scraping & Search:**  
  The scraper supports robust querying of websites, intelligently handles errors (such as timeouts or connection issues), and logs detailed information in the `database/logs` folder.

- **Proxy and Error Handling:**  
  With [get_proxy_list.py](get_proxy_list.py) and [proxy_cheaker.py](proxy_cheaker.py), you can dynamically update proxies to bypass connection errors. In case of a timeout or a failure, the error gets logged and you are notified immediately.

- **Database Management:**  
  Scraped results are stored in an SQLite database along with detailed metadata, letting you keep track of every scraped item.

- **Result Export:**  
  Easily export your data into CSV or JSON formats using the GUI options.

## How to Run It

1. **Setup Your Environment:**  
   Double-click on the `run_the_scraper.bat` file. This batch script will:
   - Create a Python virtual environment (if not already present).
   - Install the required dependencies from `requirements.txt`.
   - Launch the GUI in hidden mode using `pythonw.exe`.

2. **Using the GUI:**  
   Once the GUI is launched:
   - Enter your search query and adjust filters if needed.
   - Click the "Scrape" button to start the process.
   - The results window will show scraped data and provide options to export the results.
   - Any errors during scraping are handled gracefully and shown in an alert dialog.

3. **Monitoring and Logs:**  
   - Logs are saved under the `database/logs` folder.
   - If an error occurs (for instance, a connection timeout or a database error), the logs will capture detailed error messages.  
   - See the logs for troubleshooting and connection recovery instructions.

## Troubleshooting

- **Dependency Issues:**  
  If you see an error regarding missing modules, ensure your virtual environment is active and that dependencies have been installed properly by re-running `run_the_scraper.bat`.

- **Connection Errors:**  
  If the scraper fails to connect or times out, check the log files under `database/logs` for details. The integrated proxy management may automatically retry or switch proxies.  
  In case of persistent errors, verify your internet connection and proxy settings in the project.

- **Database Errors:**  
  In situations where the database update fails, the error is logged and the application will rollback the changes to avoid corruption. Check logs for the specific database error message.

## What It Does

- **Scrapes target websites** by sending requests and processing HTML data.
- **Extracts useful data** like titles, URLs, content summaries, images, and media details.
- **Stores the data** locally in an SQLite database so that you can review or export it anytime.
- **Handles dynamic content** with advanced error handling mechanisms to ensure reliability.

With **AI Web Scraper Pro**, you can simply click on the batch script and let the tool do all the heavy lifting—from scraping to data export, keeping you informed every step of the way!

Happy Scraping!