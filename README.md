**E-sim Unofficial API**

This API provides convenient access to scraped data from the browser game [e-sim](https://alpha.e-sim.org) through a set
of predefined endpoints.  
It leverages [my scraper library](https://pypi.org/project/e-sim-game-scraper/) for efficient data retrieval and
presentation.

## Key Features:

* **Extensive Data Coverage:** Access various E-sim data points through designated base links, including information on
  laws, countries, citizens, companies, and more.
* **Additional Data Sources:** Explore data beyond the official e-sim API through additional links derived from the
  project's database.
* **User-Friendly Endpoints:** Navigate the API effortlessly using intuitive base URLs and clear endpoint structures,
  similar to the official e-sim html pages.
* **Open-Source Project:** Contribute to the project's development and enhancements on
  GitHub: https://github.com/akiva-skolnik/e-sim-api

## API Usage:

1. **Base URL:** Prefix any supported E-sim page URL with the following base URL: https://23.95.130.52:5000/

2. **Example:** To access the details of a specific law (https://alpha.e-sim.org/law.html?id=1), use the following API
   endpoint:

https://23.95.130.52:5000/https://alpha.e-sim.org/law.html?id=1

### Notes:

* **Request Processing:** Be mindful that each API request incurs double the processing time compared to directly
  scraping the HTML, as the server fetches and transmits the data.
* **Faster Alternative:** For higher performance, consider utilizing the source code directly through
  the [e-sim-game-scraper project](https://github.com/akiva-skolnik/e-sim-game-scraper).

### Additional Information:

* Remember that additional links based on the project's database might occasionally become outdated during server
  migrations.
* The API is hosted on a server funded by satisfied users. If you find it useful, consider supporting further
  development through [Buy Me a Coffee](https://www.buymeacoffee.com/ripEsim).
