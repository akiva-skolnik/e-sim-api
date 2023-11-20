import json
from datetime import datetime

from e_sim_game_scrapper import EsimScraper
from e_sim_game_scrapper import utils as EsimScraperUtils
from flask import Flask, redirect, render_template, request
from waitress import serve
from werkzeug.exceptions import HTTPException

import utils

app = Flask(__name__)


@app.before_request
def save_count():
    """Saves the number of times each API was called to the database"""
    api_count = utils.find_one("collection", "api_count")
    if "e-sim.org/" in request.full_path:
        base_link = request.full_path[1:].split("e-sim.org/")[1].split(".html")[0]
    else:
        base_link = "Index"
    if base_link not in api_count:
        api_count[base_link] = 0
    api_count[base_link] += 1

    utils.replace_one("collection", "api_count", api_count)


@app.errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })
    response.content_type = "application/json"
    return response


@app.route('/', methods=['GET'])
@app.route('/index', methods=['GET'])
def home():
    """Displays a list of all the available APIs"""
    not_esim_links = ["prices", "monetaryMarketHistory", "buffs", "timeOnline"]
    esim_links = []
    for x in app.url_map.iter_rules():
        if "e-sim.org" in str(x):
            link = str(x).split("e-sim.org/")[-1].split(".html")[0]
            if link not in not_esim_links:
                esim_links.append(link)
    esim_links.sort()
    return render_template('index.html', esim_links=esim_links, not_esim_links=not_esim_links, base_url=request.base_url)


@app.route('/<https>://<server>.e-sim.org/prices.html', methods=['GET'])
def prices(https, server):
    """Returns dict of the top 5 offers per product in the format:
    `{str(product): [
            {"country": str(country), "link": productMarketLink, "monetary market": MM_link, "price": float(price), "stock": int(stock)}
            ]}`
    with one key being `last update`

    If `resource` is provided, returns the history of prices for that resource in the format: (last 200 records)
    `{str(date): [{"price": float(price), "record_count": int(record_count)}]}`
    (where `date` is in the format `DD-MM-YYYY`)
    """
    resource = request.args.get('resource')
    q = int(request.args.get('quality', 0))
    if resource:
        results = utils.find_one("prices_history", (f"Q{q}_" if q else "") + resource.capitalize())[server]
        results = sorted(results.items(), key=lambda x: datetime.strptime(x[0], "%d-%m-%Y"))
        limit = 200
        results = {date: [{"price": float(k), "record_count": v} for k, v in d.items()]
                   for index, (date, d) in enumerate(results) if len(results) - index <= limit}
        return utils.prepare_request(results)
    results = utils.find_one("price", server)
    results["Headers"] = results["Product"][0]
    del results["Product"]
    for product in results:
        if product == "Headers":
            continue
        for num, first_5 in enumerate(results[product]):
            DICT = {}
            for index, column in enumerate(first_5):
                DICT[results["Headers"][index].lower()] = column
            try:
                results[product][num] = DICT
            except:
                pass

    results["last update"] = " ".join(results["Headers"][-1].split()[2:4])
    del results["Headers"]
    return utils.prepare_request(results)


@app.route('/<https>://<server>.e-sim.org/monetaryMarketHistory.html', methods=['GET'])
def monetaryMarketHistory(https, server):
    """Returns dict of current prices in the format: `{str(countryId): float(price)}` with one key being `last_update`
    If `countryId` is provided, returns the history of prices for that country in the format: (last 200 records)
    `{str(date): [{"price": float(price), "times": int(times)}]}`
    (where `date` is in the format `DD-MM-YYYY` and `times` is the number of times that price was recorded on that date)
    """
    country_id = request.args.get('countryId')
    if country_id:
        results = utils.find_one("mm_history", server)[country_id]
        results = sorted(results.items(), key=lambda x: datetime.strptime(x[0], "%d-%m-%Y"))
        limit = 200
        results = {date: [{"price": float(k), "times": v} for k, v in d.items()]
                   for index, (date, d) in enumerate(results) if len(results) - index <= limit}
    else:
        results = utils.find_one("mm", server)
    return utils.prepare_request(results)


@app.route('/<https>://<server>.e-sim.org/buffs.html', methods=['GET'])
def buffs(https, server):
    """Returns dict of all the buffed players in the format:
    `[{"link": str(link), "citizenship": str(citizenship), "total_dmg": str(total_dmg with commas),
     "last_online": str(last time the player was online), "premium": bool(premium),
    "buffed_at": str(when the player buffed), "debuff_ends": DD-MM-YYYY HH:MM:SS, "till_status_change": HH:MM:SS,
    "jinxed": (-)HH:MM:SS (time left to end buff/debuff), "finese": HH:MM:SS, "bloodymess": HH:MM:SS, "lucky": HH:MM:SS}]`
    """
    results = utils.find_one("buffs", server)
    del results["Nick"]  # remove headers
    results = [{"nick": k, "link": v[0], "citizenship": v[1], "total_dmg": v[2], "last_online": v[3], "premium": v[4],
                "buffed_at": v[5], "debuff_ends": v[6], "till_status_change": v[7], "jinxed": v[8], "finese": v[9],
                "bloodymess": v[10], "lucky": v[11]} for k, v in results.items() if v[2]]  # remove empty rows
    return utils.prepare_request(results)


@app.route('/<https>://<server>.e-sim.org/timeOnline.html', methods=['GET'])
def timeOnline(https, server):
    """Returns dict of first 500 players in the format:
    `{str(citizen_id): {"nick": str(nick), "Citizenship": str(citizenship),
      "Avg. per day": HH:MM (average time online per day),
      "Minutes online (since X)": int(minutes online), "Minutes online (this month)": int(minutes online),
        "Avg. per day (time_online)": HH:MM (average time online per day in the last month)}
     }`
    """

    results = utils.find_one("time_online", server)
    headers = results["_headers"]
    headers[-1] = "Avg. per day (this month)"  # there are two keys with the same name (Avg. per day)
    del results["_headers"]
    limit = 500
    results = {citizen_id: dict(zip(headers, values)) for index, (citizen_id, values) in enumerate(
        results.items()) if index < limit}
    return utils.prepare_request(results)


@app.route('/<https>://<server>.e-sim.org/statistics.html', methods=['GET'])
def statistics(https, server):
    # locked to registered users.
    return redirect(EsimScraperUtils.redirect_statistics(request.url))


@app.route('/<https>://<server>.e-sim.org/article.html', methods=['GET'])
def article(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.article(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/auction.html', methods=['GET'])
def auction(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.auction(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/showShout.html', methods=['GET'])
def showShout(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.showShout(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/law.html', methods=['GET'])
def law(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.law(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/congressElections.html', methods=['GET'])
def congressElections(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.congressElections(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/presidentalElections.html', methods=['GET'])
def presidentalElections(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.presidentalElections(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/battleDrops.html', methods=['GET'])
def battleDrops(https, server):
    link = utils.get_link(https, request)
    tree = utils.get_tree(link)
    result = EsimScraper.battleDrops(tree, link)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/jobMarket.html', methods=['GET'])
def jobMarket(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.jobMarket(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/newCitizens.html', methods=['GET'])
def newCitizens(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.newCitizens(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/region.html', methods=['GET'])
def region(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.region(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/monetaryMarket.html', methods=['GET'])
def monetaryMarket(https, server):
    link = utils.get_link(https, request).replace(".html", "Offers")
    if link.endswith("Offers"):
        link += "?buyerCurrencyId=1&sellerCurrencyId=0&page=1"
    else:
        if "sellerCurrencyId" not in link:
            link += "&sellerCurrencyId=0"
        if "page" not in link:
            link += "&page=1"
    tree = utils.get_tree(link)
    result = EsimScraper.monetaryMarket(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/stockCompany.html', methods=['GET'])
def stockCompany(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.stockCompany(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/stockCompanyProducts.html', methods=['GET'])
def stockCompanyProducts(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.stockCompanyProducts(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/stockCompanyMoney.html', methods=['GET'])
def stockCompanyMoney(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.stockCompanyMoney(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/achievement.html', methods=['GET'])
def achievement(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.achievement(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/countryEconomyStatistics.html', methods=['GET'])
def countryEconomyStatistics(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.countryEconomyStatistics(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/citizenStatistics.html', methods=['GET'])
def citizenStatistics(https, server):
    link = utils.get_link(https, request)
    tree = utils.get_tree(link)
    result = EsimScraper.citizenStatistics(tree, link)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/stockCompanyStatistics.html', methods=['GET'])
def stockCompanyStatistics(https, server):
    link = utils.get_link(https, request)
    tree = utils.get_tree(link)
    result = EsimScraper.stockCompanyStatistics(tree, link)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/countryStatistics.html', methods=['GET'])
def countryStatistics(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.countryStatistics(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/coalitionStatistics.html', methods=['GET'])
def coalitionStatistics(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.coalitionStatistics(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/newCitizenStatistics.html', methods=['GET'])
def newCitizenStatistics(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.newCitizenStatistics(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/partyStatistics.html', methods=['GET'])
def partyStatistics(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.partyStatistics(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/newspaperStatistics.html', methods=['GET'])
def newspaperStatistics(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.newspaperStatistics(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/news.html', methods=['GET'])
def news(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.news(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/events.html', methods=['GET'])
def events(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.events(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/companiesForSale.html', methods=['GET'])
def companiesForSale(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.companiesForSale(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/countryPoliticalStatistics.html', methods=['GET'])
def countryPoliticalStatistics(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.countryPoliticalStatistics(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/newspaper.html', methods=['GET'])
def newspaper(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.newspaper(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/party.html', methods=['GET'])
def party(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.party(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/productMarket.html', methods=['GET'])
def productMarket(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.productMarket(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/battlesByWar.html', methods=['GET'])
def battlesByWar(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.battlesByWar(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/battles.html', methods=['GET'])
def battles(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.battles(tree)
    return utils.prepare_request(result)


@app.route('/<https>://<server>.e-sim.org/profile.html', methods=['GET'])
def profile(https, server):
    tree = utils.get_tree(utils.get_link(https, request))
    result = EsimScraper.profile(tree)
    return utils.prepare_request(result)


if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
