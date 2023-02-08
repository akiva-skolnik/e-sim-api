import json
from datetime import date, timedelta
from itertools import islice

import requests
from flask import Flask, redirect, request
from lxml.html import fromstring
from waitress import serve
from werkzeug.exceptions import HTTPException

import utils

requests.packages.urllib3.disable_warnings()
app = Flask(__name__)


@app.before_request
def save_count():
    api_count = utils.find_one("collection", "api count")
    if "e-sim.org/" in request.full_path:
        link = request.full_path[1:].split("e-sim.org/")[1].split(".html")[0]
    else:
        link = "Index"
    if link not in api_count:
        api_count[link] = 0
    api_count[link] += 1

    utils.replace_one("collection", "api count", dict(sorted(api_count.items(), key=lambda kv: kv[1], reverse=True)))


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
    page = '''<!DOCTYPE html>
<html>
<head>
<title>E-sim Unofficial API</title>

<h1>E-sim unofficial API</h1>
<hr>
<h2>Available base links:</h2>
<ul>'''
    links = ["<li>" + str(x).split("e-sim.org/")[1].split(".html")[0] + "</li>" for x in app.url_map.iter_rules() if
             "e-sim.org" in str(x)]
    links.sort()
    page += "".join(links)
    page += f'''</ul>
<hr>
<h1>Usage:</h1>
<p>Add the following prefix to any of the above pages:
<p><a href={request.base_url}>{request.base_url}</a>
<p><b>Example:</b>
<p><a href={request.base_url}https://alpha.e-sim.org/law.html?id=1>{request.base_url}https://secura.e-sim.org/law.html?id=1</a>
<hr>
<h1>Source Code:</h1>
<p><a href=https://github.com/akiva0003/e-sim-api/blob/main/app.py>GitHub</a></p>
Powered by <a href=https://www.patreon.com/ripEsim>Akiva</a>
<hr>
<b><p>Keep in mind that each request takes twice as much as if you would scrape the html by yourself.
<p>Also note that first request may take a while and may even throw an error, because it takes the server a few seconds to "warm up"</b>
<hr>
</body>
</html>
'''
    return page


@app.route('/<https>://<server>.e-sim.org/prices.html', methods=['GET'])
def prices(https, server):
    resource = request.args.get('resource')
    q = int(request.args.get('quality', 0))
    if resource:
        row = utils.find_one("prices_history", (f"Q{q} " if q else "") + resource.capitalize())[server]
        return utils.prepare_request(
            {date: [{"price": float(k), "record_count": v} for k, v in d.items()] for date, d in row.items()})
    row = utils.find_one("price", server)
    row["Headers"] = row["Product"][0]
    del row["Product"]
    for product in row:
        if product == "Headers":
            continue
        for num, first_5 in enumerate(row[product]):
            DICT = {}
            for index, column in enumerate(first_5):
                DICT[row["Headers"][index].lower()] = column
            try:
                row[product][num] = DICT
            except:
                pass

    row["last update"] = " ".join(row["Headers"][-1].split()[2:4])
    del row["Headers"]
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/MM.html', methods=['GET'])
def MM(https, server):
    country_id = request.args.get('countryId')
    if country_id:
        row = utils.find_one("mm_history", server)[country_id]
        row = {date: [{"price": float(k), "times": v} for k, v in d.items()] for date, d in row.items()}
    else:
        row = utils.find_one("mm", server)
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/buffs.html', methods=['GET'])
def buffs(https, server):
    row = utils.find_one("buffs", server)
    del row["Nick"]
    row = [{"nick": k, "link": v[0], "citizenship": v[1], "total_dmg": v[2], "last_online": v[3], "premium": v[4],
            "buffed_at": v[5],
            "debuff_ends": v[6], "till_status_change": v[7], "jinxed": v[8], "finese": v[9], "bloodymess": v[10],
            "lucky": v[11]} for k, v in row.items() if v[2]]
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/timeOnline.html', methods=['GET'])
def time_online(https, server):
    row = utils.find_one("time_online", server)
    headers = row["_headers"]
    del row["_headers"]
    row = {nick: dict(zip(headers, values)) for nick, values in
           islice(row.items(), 1000)}
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/statistics.html', methods=['GET'])
def statistics(https, server):
    # locked to registered users.
    return redirect(request.url.replace("statistics.html?selectedSite=" + request.args[
        "selectedSite"], utils.camelCase(request.args["selectedSite"]) + "Statistics.html").replace("&", "?", 1))


@app.route('/<https>://<server>.e-sim.org/article.html', methods=['GET'])
def article(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    posted = " ".join(tree.xpath('//*[@class="mobile_article_preview_width_fix"]/text()')[0].split()[1:-1])
    title = tree.xpath('//*[@class="articleTitle"]/text()')[0]
    subs, votes = [int(x.strip()) for x in tree.xpath('//*[@class="bigArticleTab"]/text()')]
    author_name, newspaper_name = tree.xpath('//*[@class="mobileNewspaperStatus"]/a/text()')
    author_id = int(utils.get_ids_from_path(tree, '//*[@id="mobileNewspaperStatusContainer"]/div[1]/a')[0])
    newspaper_id = int(tree.xpath('//*[@class="mobileNewspaperStatus"]/a/@href')[-1].split("=")[1])
    row = {"posted": posted, "title": title, "author": author_name.strip(), "author id": author_id, "votes": votes,
           "newspaper": newspaper_name, "newspaper_id": newspaper_id, "subs": subs}
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/auction.html', methods=['GET'])
def auction(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    seller = tree.xpath("//div[1]//table[1]//tr[2]//td[1]//a/text()")[0]
    buyer = tree.xpath("//div[1]//table[1]//tr[2]//td[2]//a/text()") or ["None"]
    item = tree.xpath("//*[@id='esim-layout']//div[1]//tr[2]//td[3]/b/text()")
    if not item:
        item = [x.strip() for x in tree.xpath("//*[@id='esim-layout']//div[1]//tr[2]//td[3]/text()") if x.strip()]
    price = float(tree.xpath("//div[1]//table[1]//tr[2]//td[4]//b//text()")[0])
    bidders = int(tree.xpath('//*[@id="esim-layout"]//div[1]//table//tr[2]//td[5]/b')[0].text)
    time1 = tree.xpath('//*[@id="esim-layout"]//div[1]//table//tr[2]//td[6]/span/text()')
    if not time1:
        time1 = [x.strip() for x in tree.xpath('//*[@id="esim-layout"]//div[1]//table//tr[2]//td[6]/text()') if
                 x.strip()]
        reminding_seconds = -1
    else:
        time1 = [int(x) for x in time1[0].split(":")]
        reminding_seconds = time1[0] * 60 * 60 + time1[1] * 60 + time1[2]
        time1 = [f'{time1[0]:02d}:{time1[1]:02d}:{time1[2]:02d}']
    row = {"seller": seller.strip(), "buyer": buyer[0].strip(), "item": item[0],
           "price": price, "time": time1[0], "bidders": bidders, "reminding_seconds": reminding_seconds}
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/showShout.html', methods=['GET'])
def showShout(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    shout = [x.strip() for x in tree.xpath('//*[@class="shoutContainer"]//div//div[1]//text()') if x.strip()]
    shout = "\n".join([x.replace("★", "") for x in shout]).strip()
    author = tree.xpath('//*[@class="shoutAuthor"]//a/text()')[0].strip()
    posted = tree.xpath('//*[@class="shoutAuthor"]//b')[0].text
    row = {"body": shout, "author": author, "posted": posted.replace("posted ", "")}
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/law.html', methods=['GET'])
def law(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    time1 = tree.xpath('//*[@id="esim-layout"]//script[3]/text()')[0]
    time1 = [i.split(");\n")[0] for i in time1.split("() + ")[1:]]
    if int(time1[0]) < 0:
        time1 = "Voting finished"
    else:
        time1 = f'{int(time1[0]):02d}:{int(time1[1]):02d}:{int(time1[2]):02d}'
    proposal = " ".join([x.strip() for x in tree.xpath('//table[1]//tr[2]//td[1]//div[2]//text()')]).strip()
    by = tree.xpath('//table[1]//tr[2]//td[3]//a/text()')[0]
    yes = [x.strip() for x in tree.xpath('//table[2]//td[2]//text()') if x.strip()][0]
    no = [x.strip() for x in tree.xpath('//table[2]//td[3]//text()') if x.strip()][0]
    time2 = tree.xpath('//table[1]//tr[2]//td[3]//b')[0].text
    row = {"law_proposal": proposal, "proposed_by": by.strip(), "proposed": time2,
           "remaining_time" if "Voting finished" not in time1 else "status": time1, "yes": int(yes), "no": int(no)}
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/congressElections.html', methods=['GET'])
def congressElections(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    country = tree.xpath('//*[@id="countryId"]//option[@selected="selected"]')[0].text
    country_id = int(tree.xpath('//*[@id="countryId"]//option[@selected="selected"]/@value')[0])
    date = tree.xpath('//*[@id="date"]//option[@selected="selected"]')[0].text
    candidates = tree.xpath("//tr//td[2]//a/text()")
    candidates_ids = utils.get_ids_from_path(tree, "//tr//td[2]//a")
    parties = tree.xpath("//tr//td[4]//div/a/text()")
    parties_links = tree.xpath("//tr//td[4]//div/a/@href")
    votes = [x.replace("-", "0").strip() for x in tree.xpath("//tr[position()>1]//td[5]//text()") if x.strip()] or [
        0] * len(candidates)

    row = {"country": country, "country_id": country_id, "date": date, "candidates": []}
    for candidate, candidate_id, vote, party_name, party_id in zip(candidates, candidates_ids, votes, parties,
                                                                   parties_links):
        row["candidates"].append(
            {"candidate": candidate.strip(), "candidate_id": int(candidate_id), "votes": int(vote.strip()),
             "party_name": party_name, "party_id": int(party_id.split("id=")[1])})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/presidentalElections.html', methods=['GET'])
def presidentalElections(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    country = tree.xpath('//*[@id="countryId"]//option[@selected="selected"]')[0].text
    country_id = int(tree.xpath('//*[@id="countryId"]//option[@selected="selected"]/@value')[0])
    date = tree.xpath('//*[@id="date"]//option[@selected="selected"]')[0].text
    candidates = tree.xpath("//tr//td[2]//a/text()")
    candidates_ids = utils.get_ids_from_path(tree, "//tr//td[2]//a")
    votes = [x.replace("-", "0").strip() for x in tree.xpath("//tr[position()>1]//td[4]//text()") if x.strip()] or [
        0] * len(candidates)
    row = {"country": country, "country_id": country_id, "date": date, "candidates": []}
    for candidate, vote, candidate_id in zip(candidates, votes, candidates_ids):
        row["candidates"].append(
            {"candidate": candidate.strip(), "votes": int(vote.strip()), "candidate_id": int(candidate_id)})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/battleDrops.html', methods=['GET'])
def battleDrops(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    last_page = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href") or ['page=1']
    last_page = int(last_page[0].split('page=')[1])
    row = {"pages": last_page, "drops": []}
    if "showSpecialItems" in request.full_path:
        nicks = tree.xpath("//tr[position()>1]//td[2]//a/text()")
        items = [x.strip() for x in tree.xpath("//tr[position()>1]//td[1]//text()") if x.strip()]
        ids = utils.get_ids_from_path(tree, "//tr[position()>1]//td[2]//a")
        for nick, item, citizen_id in zip(nicks, items, ids):
            row["drops"].append({"nick": nick.strip(), "item": item, "citizen_id": int(citizen_id)})
    else:
        nicks = tree.xpath("//tr[position()>1]//td[4]//a/text()")
        qualities = tree.xpath("//tr[position()>1]//td[2]/text()")
        items = tree.xpath("//tr[position()>1]//td[3]/text()")
        ids = utils.get_ids_from_path(tree, "//tr[position()>1]//td[4]//a")
        for nick, quality, item, citizen_id in zip(nicks, qualities, items, ids):
            row["drops"].append({"nick": nick.strip(), "citizen_id": int(citizen_id), "item": item.strip(),
                                 "quality": int(quality.replace("Q", ""))})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/jobMarket.html', methods=['GET'])
def jobMarket(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    country = tree.xpath('//*[@id="countryId"]//option[@selected="selected"]')[0].text
    country_id = int(tree.xpath('//*[@id="countryId"]//option[@selected="selected"]/@value')[0])
    employers = tree.xpath('//*[@id="esim-layout"]//td[1]/a/text()')
    companies = tree.xpath('//*[@id="esim-layout"]//td[2]/a/text()')
    companies_link = tree.xpath('//*[@id="esim-layout"]//td[2]/a/@href')
    company_types = []
    qualities = []
    products = tree.xpath('//*[@id="esim-layout"]//td[3]/div/div/img/@src')
    for p in utils.chunker(products, 2):
        product, quality = [x.split("/")[-1].split(".png")[0] for x in p]
        product = product.replace("Defense System", "Defense_System").strip()
        quality = quality.replace("q", "").strip()
        company_types.append(product)
        qualities.append(int(quality))
    skills = tree.xpath('//*[@id="esim-layout"]//tr[position()>1]//td[4]/text()')
    salaries = tree.xpath('//*[@id="esim-layout"]//td[5]/b/text()')
    row = {"country": country, "country_id": country_id, "offers": []}
    for employer, company, company_link, company_type, quality, skill, salary in zip(
            employers, companies, companies_link, company_types, qualities, skills, salaries):
        row["offers"].append(
            {"employer": employer.strip(), "company": company, "company_id": int(company_link.split("?id=")[1]),
             "company_type": company_type, "company_quality": int(quality),
             "minimal_skill": int(skill), "salary": float(salary)})
    row["cc"] = tree.xpath('//*[@id="esim-layout"]//tr[2]//td[5]/text()')[-1].strip() if row["offers"] else ""
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/newCitizens.html', methods=['GET'])
def newCitizens(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    country = tree.xpath('//*[@id="countryId"]//option[@selected="selected"]')[0].text
    country_id = int(tree.xpath('//*[@id="countryId"]//option[@selected="selected"]/@value')[0])
    nicks = tree.xpath('//td[1]/a/text()')
    levels = tree.xpath('//tr[position()>1]//td[2]/text()')
    experiences = tree.xpath('//tr[position()>1]//td[3]/text()')
    registered = tree.xpath('//tr[position()>1]//td[4]/text()')
    locations = tree.xpath('//tr[position()>1]//td[5]/a/text()')
    location_links = tree.xpath('//td[5]/a/@href')
    ids = utils.get_ids_from_path(tree, "//td[1]/a")
    row = {"country": country, "country_id": country_id, "new_citizens": []}
    for nick, level, experience, registered, location, location_link, citizen_id in zip(
            nicks, levels, experiences, registered, locations, location_links, ids):
        row["new_citizens"].append(
            {"nick": nick, "level": int(level.strip()), "experience": int(experience.strip()),
             "registered": registered.strip(), "region": location, "location_id": int(location_link.split("?id=")[1]),
             "citizen_id": int(citizen_id)})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/region.html', methods=['GET'])
def region(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    owner = tree.xpath('//*[@id="esim-layout"]//div[1]//tr[2]//td[1]//span')[0].text
    rightful_owner = tree.xpath('//*[@id="esim-layout"]//div[1]//tr[2]//td[2]//span')[0].text
    region_name = tree.xpath('//*[@id="esim-layout"]//h1')[0].text.replace("Region ", "")
    try:
        resource_type = \
        tree.xpath('//*[@id="esim-layout"]//div[1]//tr[2]//td[3]/div/div/img/@src')[0].split("/")[-1].split(".png")[0]
    except:
        resource_type = "No resources"
    resource = tree.xpath('//*[@id="esim-layout"]//div[1]//tr[2]//td[3]/b')
    resource = resource[0].text if resource else "No resources"
    population = tree.xpath('//*[@id="esim-layout"]//div[1]//tr[2]//td[4]/b')[0].text
    active_companies, all_companies = tree.xpath('//*[@id="esim-layout"]//div[1]//tr[2]//td[5]/b')[0].text.split()

    is_occupied = tree.xpath('//*[@id="esim-layout"]//div[2]//b[1]/text()')
    base_div = 3 if len(is_occupied) == 1 else 2
    industry = tree.xpath(f'//*[@id="esim-layout"]//div[{base_div}]//table[1]//b[1]/text()')
    industry = dict(zip(industry[::2], [float(x) for x in industry[1::2]]))
    companies_type = tree.xpath('//*[@id="esim-layout"]//table[2]//td[1]/b/text()')
    total_companies = [x.strip() for x in tree.xpath('//*[@id="esim-layout"]//table[2]//tr[position()>1]//td[2]/text()')
                       if x.strip()]
    values = tree.xpath('//*[@id="esim-layout"]//table[2]//td[3]/b/text()')
    penalties = tree.xpath('//*[@id="esim-layout"]//table[2]//tr[position()>1]//td[4]/text()') or ["100%"] * len(values)

    active = [{"type": company_type, "total companies": int(total_companies.strip()), "value": float(value),
               "penalty": penalty.strip()}
              for company_type, total_companies, value, penalty in
              zip(companies_type, total_companies, values, penalties)]

    rounds = tree.xpath('//*[@id="esim-layout"]//table[2]//td[2]/b/text()')
    buildings = tree.xpath('//*[@id="esim-layout"]//table[2]//td[1]/div/div/img/@src')
    building_places = {}
    for round_number, p in zip(rounds, utils.chunker(buildings, 2)):
        building, quality = [x.split("/")[-1].split(".png")[0] for x in p]
        building = building.replace("Defense System", "Defense_System").strip()
        building_places[int(round_number)] = f"{quality.strip().upper()} {building}"

    row = {"region": region_name, "active_companies_stats": active,
           "buildings": [{"round": k, "building": v} for k, v in building_places.items()],
           "industry": [{"company": k, "total_value": v} for k, v in industry.items()], "current_owner": owner,
           "rightful_owner": rightful_owner, "resource": resource_type, "resource_richness": resource,
           "population": int(population),
           "active_companies": int(active_companies),
           "total_companies": int(all_companies.replace("(", "").replace(")", ""))}
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/monetaryMarket.html', methods=['GET'])
def monetaryMarket(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    buy = tree.xpath('//*[@id="buy"]//option[@selected="selected"]')[0].text
    sell = tree.xpath('//*[@id="sell"]//option[@selected="selected"]')[0].text
    sellers = tree.xpath("//td[1]/a/text()")
    seller_ids = [int(x.split("?id=")[1]) for x in tree.xpath("//td[1]/a/@href")]
    amounts = tree.xpath("//td[2]/b/text()")
    ratios = tree.xpath("//td[3]/b/text()")
    offers_ids = [int(x.value) for x in tree.xpath("//td[4]//form//input[2]")]
    row = {"buy": buy, "sell": sell, "offers": []}
    for seller, seller_id, amount, ratio, offer_id in zip(sellers, seller_ids, amounts, ratios, offers_ids):
        row["offers"].append({"seller": seller.strip(), "seller_id": seller_id,
                              "amount": float(amount), "ratio": float(ratio), "offer_id": offer_id})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/stockCompany.html', methods=['GET'])
def stockCompany(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    sc_name = tree.xpath("//span[@class='big-login']")[0].text
    ceo = (tree.xpath('//*[@id="partyContainer"]//div//div[1]//div//div[1]//div[2]/a/text()') or ["No CEO"])[0].strip()
    ceo_status = tree.xpath('//*[@id="partyContainer"]//div//div[1]//div//div[1]//div[2]//a/@style') or [
        "Active" if ceo != "No CEO" else ""]
    ceo_status = ceo_status[0].replace("color: #f00; text-decoration: line-through;", "Banned").replace(
        "color: #888;", "Inactive")
    main = [float(x) for x in tree.xpath('//*[@class="muColEl"]//b/text()')]
    try:
        price = tree.xpath('//*[@id="esim-layout"]//tr//td[2]//div[1]//table[1]//td[2]/b/text()')
        price = [float(x) for x in price]
        stock = tree.xpath('//*[@id="esim-layout"]//tr//td[2]//div[1]//table[1]//td[1]/b/text()')
        stock = [int(x) for x in stock]
    except:
        price, stock = [], []
    offers = [{"amount": stock, "price": price} for stock, price in zip(stock, price)]
    try:
        last_transactions_amount = tree.xpath('//*[@id="esim-layout"]//tr//td[2]//div[1]//table[3]//td[1]/b/text()')
        last_transactions_price = tree.xpath('//*[@id="esim-layout"]//tr//td[2]//div[1]//table[3]//td[2]/b/text()')
        last_transactions_time = tree.xpath(
            '//*[@id="esim-layout"]//tr//td[2]//div[1]//table[3]//tr[position()>1]//td[3]/text()')
    except:
        last_transactions_amount, last_transactions_price, last_transactions_time = [], [], []
    header = ["total_shares", "total_value", "price_per_share", "daily_trade_value", "shareholders", "companies",
              # main
              "sc_name", "ceo", "ceo_status", "offers"]
    data = main + [sc_name, ceo, ceo_status, offers]
    last_transactions = [{"amount": int(a.strip()), "price": float(b.strip()), "time": c.strip()} for a, b, c in zip(
        last_transactions_amount, last_transactions_price, last_transactions_time)]
    row = dict(zip(header, data))
    row["last_transactions"] = last_transactions
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/stockCompanyProducts.html', methods=['GET'])
def stockCompanyProducts(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    row = {}
    amount = [int(x.strip()) for x in tree.xpath('//*[@id="esim-layout"]//center//div//div//div[1]/text()')]
    products = [x.split("/")[-1].split(".png")[0] for x in
                tree.xpath('//*[@id="esim-layout"]//center//div//div//div[2]//img[1]/@src')]
    for index, product in enumerate(products):
        quality = tree.xpath(f'//*[@id="esim-layout"]//center//div//div[{index + 1}]//div[2]//img[2]/@src')
        if "Defense System" in product:
            product = product.replace("Defense System", "Defense_System")
        if quality:
            products[index] = f'{quality[0].split("/")[-1].split(".png")[0].upper()} {product}'
    row["storage"] = [{"product": product, "amount": amount} for product, amount in zip(products, amount)]

    amount = [int(x.strip()) for x in tree.xpath('//*[@id="esim-layout"]//div[2]//table//tr//td[3]/text()')[1:]]
    gross_price = tree.xpath('//*[@id="esim-layout"]//div[2]//table//tr//td[4]/b/text()')
    coin = [x.strip() for x in tree.xpath('//*[@id="esim-layout"]//div[2]//table//tr//td[4]/text()')[1:] if x.strip()]
    net_price = tree.xpath('//*[@id="esim-layout"]//div[2]//table//tr//td[5]/b/text()')
    products = [x.split("/")[-1].split(".png")[0] for x in
                tree.xpath('//*[@id="esim-layout"]//div[2]//table//tr//td[1]//img[1]/@src')]
    for index, product in enumerate(products):
        quality = tree.xpath(f'//*[@id="esim-layout"]//div[2]//table//tr[{index + 2}]//td[1]//img[2]/@src')
        if "Defense System" in product:
            product = product.replace("Defense System", "Defense_System")
        if quality:
            products[index] = f'{quality[0].split("/")[-1].split(".png")[0].upper()} {product}'
    row["offers"] = []
    for product, amount, gross_price, coin, net_price in zip(products, amount, gross_price, coin, net_price):
        row["offers"].append(
            {"product": product, "amount": amount, "gross price": float(gross_price),
             "coin": coin, "net price": float(net_price)})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/stockCompanyMoney.html', methods=['GET'])
def stockCompanyMoney(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    coins = [x.strip() for x in tree.xpath('//*[@id="esim-layout"]//div[3]//div/text()') if x.strip()]
    stock = tree.xpath('//*[@id="esim-layout"]//div[3]//div//b/text()')
    row = {"storage": [{k: float(v) for k, v in zip(coins, stock)}]}

    amounts = [float(x) for x in tree.xpath('//*[@id="esim-layout"]//div[4]//table//tr/td[2]/b/text()')]
    coins = [x.strip() for x in tree.xpath('//*[@id="esim-layout"]//div[4]//table//tr/td[2]/text()') if x.strip()][1:]
    ratios = [float(x) for x in tree.xpath('//*[@id="esim-layout"]//div[4]//table//tr/td[3]/b/text()')]
    offer_ids = [int(x.value) for x in tree.xpath('//*[@id="esim-layout"]//div[4]//table//tr/td[4]//form//input[2]')]
    row["offers"] = [{"amount": amount, "coin": coin, "ratio": ratio, "offer_id": offer_id} for
                     amount, coin, ratio, offer_id in zip(
            amounts, coins, ratios, offer_ids)]
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/achievement.html', methods=['GET'])
def achievement(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    last_page = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href") or ['page=1']
    last_page = int(last_page[0].split('page=')[1])
    ids = utils.get_ids_from_path(tree, '//*[@id="esim-layout"]//div[3]//div/a')
    nicks = [x.strip() for x in tree.xpath('//*[@id="esim-layout"]//div[3]//div/a/text()')]
    category, achieved_by = [x.split(":")[1].strip() for x in
                             tree.xpath('//*[@id="esim-layout"]//div[1]//div[2]/text()') if x.strip()]
    description = tree.xpath('//*[@class="foundation-style columns column-margin-vertical help"]/i/text()')[0].strip()
    players = [{"citizen_id": int(citizen_id), "nick": nick} for citizen_id, nick in zip(ids, nicks)]
    row = {"description": description, "category": category, "achieved by": achieved_by, "players": players,
           "pages": last_page}
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/countryEconomyStatistics.html', methods=['GET'])
def countryEconomyStatistics(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    country = tree.xpath('//*[@id="countryId"]//option[@selected="selected"]')[0].text
    country_id = int(tree.xpath('//*[@id="countryId"]//option[@selected="selected"]/@value')[0])
    links = [int(x.split("id=")[1]) for x in tree.xpath('//*[@id="esim-layout"]//table[1]//td[1]/a/@href')]
    regions = tree.xpath('//*[@id="esim-layout"]//table[1]//td[1]/a/text()')
    regions = [dict(zip(links, regions))]
    population = [x.strip().replace(":", "").replace(" ", "_").lower() for x in
                  tree.xpath('//*[@id="esim-layout"]//div[2]//div[2]//table//tr//td/text()') if x.strip()]
    minimal_salary = tree.xpath('//*[@id="esim-layout"]//div[2]//table//tr[6]//td[2]/b')[0].text
    population[-1] = minimal_salary
    population = dict(zip(population[::2], [float(x) for x in population[1::2]]))
    treasury_keys = [x.strip() for x in
                     tree.xpath('//*[@id="esim-layout"]//div[2]//div[5]//table//tr[position()>1]//td/text()') if
                     x.strip()]
    treasury_values = tree.xpath('//*[@id="esim-layout"]//div[2]//div[5]//table//tr[position()>1]//td/b/text()')
    treasury = [{k: float(v) for k, v in zip(treasury_keys, treasury_values)}]
    table = [x.strip() for x in tree.xpath('//*[@id="esim-layout"]//div[2]//div[4]//table//tr//td/text()')]
    columns = 5
    taxes = {table[columns:][i]: table[columns:][i + 1:i + columns] for i in
             range(0, len(table[columns:]) - columns, columns)}
    taxes_list = [{**dict(zip(table[1:columns], v)), **{"type": k}} for k, v in taxes.items()]
    row = {"country": country, "country_id": country_id, "borders": regions, "treasury": treasury, "taxes": taxes_list}
    row.update(population)
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/stockCompanyStatistics.html', methods=['GET'])
@app.route('/<https>://<server>.e-sim.org/citizenStatistics.html', methods=['GET'])
def citizenStatistics(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    country = tree.xpath('//*[@id="countryId"]//option[@selected="selected"]')[0].text
    try:
        statistic_type = tree.xpath('//*[@name="statisticType"]//option[@selected="selected"]')[0].text
    except:
        statistic_type = tree.xpath('//*[@name="statisticType"]//option[1]')[0].text
    country_id = int(tree.xpath('//*[@id="countryId"]//option[@selected="selected"]/@value')[0])
    ids = utils.get_ids_from_path(tree, "//td/a")
    nicks = tree.xpath("//td/a/text()")
    countries = tree.xpath("//td[3]/b/text()")
    values = tree.xpath("//tr[position()>1]//td[4]/text()") if "citizenStatistics" in request.full_path else tree.xpath(
        "//tr[position()>1]//td[4]/b/text()")
    for index, parameter in enumerate(values):
        value = ""
        for char in parameter:
            if char in "1234567890.":
                value += char
        if value:
            values[index] = float(value)

    row = {"country": country, "country_id": country_id, "statistic_type": statistic_type,
           "citizens" if "citizenStatistics" in request.full_path else "stock_companies": [
               {"id": int(key_id),
                "nick" if "citizenStatistics" in request.full_path else "stock_company": nick.strip(),
                "country": country, statistic_type.lower(): value} for key_id, nick, country, value in
               zip(ids, nicks, countries, values)]}
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/countryStatistics.html', methods=['GET'])
def countryStatistics(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    statistic_type = tree.xpath('//*[@name="statisticType"]//option[@selected="selected"]')[0].text
    countries = tree.xpath("//td/b/text()")[1:]
    values = tree.xpath("//td[3]/text()")[1:]
    row = {"statistic_type": statistic_type,
           "countries": [{"country": k, statistic_type.lower(): int(v.replace(",", "").strip())} for k, v in
                         zip(countries, values)]}
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/coalitionStatistics.html', methods=['GET'])
def coalitionStatistics(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    row = []
    for tr in range(2, 103):  # First 100
        try:
            coalition_id = int(tree.xpath(f'//tr[{tr}]//td[1]//span'))
            name = tree.xpath(f'//tr[{tr}]//td[2]//span/text()') or ["-"]
            leader = tree.xpath(f'//tr[{tr}]//td[3]/a/text()') or ["-"]
            leader_id = (utils.get_ids_from_path(tree, f'//tr[{tr}]//td[3]/a/@href') or [0])[0]
            members = int(tree.xpath(f'//tr[{tr}]//td[4]//span')[0].text)
            regions = int(tree.xpath(f'//tr[{tr}]//td[5]//span')[0].text)
            citizens = int(tree.xpath(f'//tr[{tr}]//td[6]//span')[0].text)
            dmg = int(tree.xpath(f'//tr[{tr}]//td[7]//span')[0].text.replace(",", ""))
            row.append({"coalition_id": coalition_id, "name": name[0], "leader": leader[0].strip(),
                        "leader_id": int(leader_id),
                        "members": members, "regions": regions, "citizens": citizens, "dmg": dmg})
        except:
            break
    row = sorted(row, key=lambda k: k['dmg'], reverse=True)
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/newCitizenStatistics.html', methods=['GET'])
def newCitizenStatistics(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    names = [x.strip() for x in tree.xpath("//tr//td[1]/a/text()")]
    citizen_ids = [int(x.split("?id=")[1]) for x in tree.xpath("//tr//td[1]/a/@href")]
    countries = tree.xpath("//tr//td[2]/span/text()")
    registration_time = [x.strip() for x in tree.xpath("//tr[position()>1]//td[3]/text()[1]")]
    registration_time1 = tree.xpath("//tr//td[3]/text()[2]")
    xp = [int(x) for x in tree.xpath("//tr[position()>1]//td[4]/text()")]
    wep = ["479" in x for x in tree.xpath("//tr[position()>1]//td[5]/i/@class")]
    food = ["479" in x for x in tree.xpath("//tr[position()>1]//td[6]/i/@class")]
    gift = ["479" in x for x in tree.xpath("//tr[position()>1]//td[5]/i/@class")]
    row = []
    for name, citizen_id, country, registration_time, registration_time1, xp, wep, food, gift in zip(
            names, citizen_ids, countries, registration_time, registration_time1, xp, wep, food, gift):
        row.append({"name": name, "citizen_id": citizen_id, "country": country, "registration_time": registration_time,
                    "registered": registration_time1[1:-1], "xp": xp, "wep": wep, "food": food, "gift": gift})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/partyStatistics.html', methods=['GET'])
def partyStatistics(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    country = tree.xpath("//tr//td[2]/b/text()")[:50]
    party_name = tree.xpath("//tr//td[3]//div/a/text()")[:50]
    party_id = [int(x.split("?id=")[1]) for x in tree.xpath("//tr//td[3]//div/a/@href")][:50]
    prestige = [int(x) for x in tree.xpath("//tr[position()>1]//td[4]/text()")][:50]
    elected_cps = [int(x.strip()) if x.strip() else 0 for x in tree.xpath("//tr[position()>1]//td[5]/text()")][:50]
    elected_congress = [int(x.strip()) if x.strip() else 0 for x in tree.xpath("//tr[position()>1]//td[6]/text()")][:50]
    laws = [int(x.strip()) if x.strip() else 0 for x in tree.xpath("//tr[position()>1]//td[7]/text()")][:50]
    members = [int(x) for x in tree.xpath("//tr//td[8]/b/text()")][:50]
    row = []
    for country, party_name, party_id, prestige, elected_cps, elected_congress, laws, members in zip(
            country, party_name, party_id, prestige, elected_cps, elected_congress, laws, members):
        row.append({"country": country, "party": party_name, "party id": party_id, "prestige": prestige,
                    "elected_cps": elected_cps,
                    "elected_congress": elected_congress, "laws": laws, "members": members})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/newspaperStatistics.html', methods=['GET'])
def newspaperStatistics(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    last_page = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href") or ['page=1']
    last_page = int(last_page[0].split('page=')[1])
    row = {"pages": last_page, "newspapers": []}

    indexes = [int(x.strip()) for x in tree.xpath("//tr[position()>1]//td[1]/text()")]
    redactors = [x.strip() for x in tree.xpath("//tr//td[2]/a/text()")]
    redactor_ids = utils.get_ids_from_path(tree, "//tr//td[2]/a")
    newspaper_names = tree.xpath("//tr//td[3]/span/a/text()")
    newspaper_ids = [int(x.split("?id=")[1]) for x in tree.xpath("//tr//td[3]/span/a/@href")]
    subs = [int(x) for x in tree.xpath("//tr[position()>1]//td[4]/b/text()")]
    for index, redactor, redactor_id, newspaper_name, newspaper_id, sub in zip(
            indexes, redactors, redactor_ids, newspaper_names, newspaper_ids, subs):
        row["newspapers"].append({"index": index, "redactor": redactor, "redactor_id": int(redactor_id),
                                  "newspaper": newspaper_name, "newspaper_id": newspaper_id, "subs": sub})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/news.html', methods=['GET'])
def news(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    country = tree.xpath('//*[@id="country"]//option[@selected="selected"]')[0].text
    countryId = int(tree.xpath('//*[@id="country"]//option[@selected="selected"]/@value')[0])
    news_type = tree.xpath('//*[@id="newsType"]//option[@selected="selected"]')[0].text
    votes = [int(x.strip()) for x in tree.xpath('//tr//td//div[1]/text()') if x.strip()]
    titles = tree.xpath('//tr//td//div[2]/a/text()')
    links = [int(x.split("?id=")[1]) for x in tree.xpath('//tr//td//div[2]/a/@href')]
    posted = tree.xpath('//tr//td//div[2]//text()[preceding-sibling::br]')
    types, posted = [x.replace("Article type: ", "").strip() for x in posted[1::2]], \
        [x.replace("Posted", "").strip() for x in posted[::2]]
    newspaper_names = [x.strip() for x in tree.xpath('//*[@id="esim-layout"]//table//tr//td//div[3]//div/a[1]/text()')]
    newspaper_id = [int(x.split("?id=")[1]) for x in
                    tree.xpath('//*[@id="esim-layout"]//table//tr//td//div[3]//div/a[1]/@href')]
    row = {"country": country, "country_id": countryId, "news_type": news_type, "articles": []}
    for title, link, vote, posted, article_type, newspaper_name, newspaper_id in zip(
            titles, links, votes, posted, types, newspaper_names, newspaper_id):
        row["articles"].append({"title": title, "article id": link, "votes": vote, "posted": posted, "type": article_type,
                                "newspaper_name": newspaper_name, "newspaper_id": newspaper_id})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/events.html', methods=['GET'])
def events(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    last_page = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href") or ['page=1']
    last_page = int(last_page[0].split('page=')[1])
    country = tree.xpath('//*[@id="country"]//option[@selected="selected"]')[0].text
    country_id = int(tree.xpath('//*[@id="country"]//option[@selected="selected"]/@value')[0])
    events_type = tree.xpath('//*[@id="eventsType"]//option[@selected="selected"]')[0].text
    titles = [x.text_content().replace("\n\xa0 \xa0 \xa0 \xa0", "").replace("  ", " ").strip() for x in
              tree.xpath('//tr//td//div[2]')]
    titles = [x for x in titles if x]
    icons = [x.split("/")[-1].replace("Icon.png", "") for x in tree.xpath('//tr//td//div[1]//img//@src')]
    icons = [x if ".png" not in x else "" for x in icons]
    links = tree.xpath('//tr//td//div[2]/a/@href')
    row = {"country": country, "country_id": country_id, "pages": last_page, "events_type": events_type, "events": []}
    for title, link, icon in zip(titles, links, icons):
        row["events"].append(
            {"event": " ".join(title.split("  ")[:-1]).strip(), "time": title.split("  ")[-1].strip(), "link": link,
             "icon": icon})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/companiesForSale.html', methods=['GET'])
def companiesForSale(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    company_ids = [int(x.split("?id=")[1]) for x in tree.xpath('//tr//td[1]//a/@href')]
    company_names = [x.strip() for x in tree.xpath('//tr//td[1]/a/text()')]
    company_types = []
    qualities = []
    products = tree.xpath('//tr//td[2]//div//div//img/@src')
    for p in utils.chunker(products, 2):
        product, quality = [x.split("/")[-1].split(".png")[0] for x in p]
        product = product.replace("Defense System", "Defense_System").strip()
        quality = quality.replace("q", "").strip()
        company_types.append(product)
        qualities.append(int(quality))
    location_names = tree.xpath('//tr//td[3]/b/a/text()')
    countries = tree.xpath('//tr//td[3]/span[last()]/text()')
    location_ids = [int(x.split("?id=")[1]) for x in tree.xpath('//tr//td[3]//a/@href')]
    seller_ids = utils.get_ids_from_path(tree, '//tr//td[4]//a')
    seller_names = [x.replace("\xa0", "") for x in tree.xpath('//tr//td[4]//a/text()')]
    seller_types = tree.xpath('//tr//td[4]//b/text()')
    prices = [float(x.replace(" Gold", "")) for x in tree.xpath('//tr//td[5]//b/text()')]
    offer_ids = [int(x.value) for x in tree.xpath('//tr//td[6]//input[1]')]
    row = []
    for (company_id, company_name, company_types, qualities, location_name, country, location_id, seller_id,
         seller_name, seller_type, price, offer_id) in zip(
            company_ids, company_names, company_types, qualities, location_names, countries, location_ids, seller_ids,
            seller_names, seller_types, prices, offer_ids):
        row.append({"company_id": company_id, "company_name": company_name, "company_type": company_types,
                    "quality": qualities, "location_name": location_name,
                    "country": country, "location_id": location_id, "seller_id": int(seller_id),
                    "seller_name": seller_name,
                    "seller_type": seller_type, "price": price, "offer_id": offer_id})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/countryPoliticalStatistics.html', methods=['GET'])
def countryPoliticalStatistics(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    row = {}
    for minister in ["Defense", "Finance", "Social"]:
        ministry = tree.xpath(f'//*[@id="ministryOf{minister}"]//div//div[2]/a[1]/text()')
        try:
            link = int(utils.get_ids_from_path(tree, f'//*[@id="ministryOf{minister}"]//div//div[2]/a[1]')[0])
        except:
            continue
        row["minister_of_" + minister.lower()] = {"id": link, "nick": ministry[0]}

    orders = tree.xpath('//*[@id="presidentBattleOrder"]//@href')
    if len(orders) == 1:
        row["country_order"] = orders[0]
    elif len(orders) == 2:
        row["country_order"] = orders[0]
        row["coalition_order"] = orders[1]
    congress = tree.xpath('//*[@id="congressByParty"]//a/text()')
    congress_links = utils.get_ids_from_path(tree, '//*[@id="congressByParty"]//a')
    row["congress"] = [{"nick": congress.strip(), "id": int(link)} for congress, link in zip(congress, congress_links)]
    coalition = tree.xpath('//*[@id="mobileCountryPoliticalStats"]/span/text()')
    row["coalition_members"] = coalition
    sides = [x.replace("xflagsMedium xflagsMedium-", "").replace("-", " ") for x in
             tree.xpath('//table[1]//tr//td//div//div//div//div//div/@class')]
    sides = [sides[x:x + 2] for x in range(0, len(sides), 2)]
    links = tree.xpath('//table[1]//tr//td[2]/a/@href')
    row["wars"] = [{"link": link, "attacker": attacker, "defender": defender} for link, (attacker, defender) in
                   zip(links, sides)]
    naps = tree.xpath('//table[2]//tr//td/b/text()')
    naps_expires = [x.strip() for x in tree.xpath('//table[2]//tr//td[2]/text()')][1:]
    row["naps"] = [{"country": naps, "expires": naps_expires} for naps, naps_expires in zip(naps, naps_expires)]
    allies = tree.xpath('//table[3]//tr//td/b/text()')
    expires = [x.strip() for x in tree.xpath('//table[3]//tr//td[2]/text()')][1:]
    row["mpps"] = [{"country": allies, "expires": expires} for allies, expires in zip(allies, expires)]
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/newspaper.html', methods=['GET'])
def newspaper(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    titles = tree.xpath('//*[@id="esim-layout"]//table//tr//td//div[2]//a[1]/text()')
    article_ids = [int(x.split("?id=")[1]) for x in
                   tree.xpath('//*[@id="esim-layout"]//table//tr//td//div[2]//a[1]/@href')]
    posted_list = [x.replace("Posted ", "").strip() for x in
                   tree.xpath('//*[@id="esim-layout"]//table//tr//td//div[2]/text()') if x.strip()]
    votes = [int(x) for x in tree.xpath('//*[@id="esim-layout"]//table//tr//td//div[1]/text()')]
    last_page = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href") or ['page=1']
    last_page = int(last_page[0].split('page=')[1])
    subs = int(tree.xpath('//*[@id="mobileNewspaperStatusContainer"]//div[3]//div/text()')[0].strip())
    redactor = tree.xpath('//*[@id="mobileNewspaperStatusContainer"]/div[1]/a/text()')[0].strip()
    redactor_id = int(utils.get_ids_from_path(tree, '//*[@id="mobileNewspaperStatusContainer"]/div[1]//a')[0])
    row = {"subs": subs, "pages": last_page, "redactor": redactor, "redactor_id": redactor_id,
           "articles": [{"title": title, "id": article_id, "posted": posted, "votes": votes} for
                        title, article_id, posted, votes in zip(
                   titles, article_ids, posted_list, votes)]}
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/party.html', methods=['GET'])
def party(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    name = tree.xpath('//*[@id="unitStatusHead"]//div/a/text()')[0]
    country = tree.xpath('//*[@class="countryNameTranslated"]/text()')[0]
    row = {"members_list": [], "country": country, "name": name}

    for x in tree.xpath('//*[@class="muColEl"]/b/text()'):
        x = x.split(":")
        if len(x) == 2:
            x[1] = x[1].replace(",", "").strip()
            if x[1]:
                row[x[0].replace(" ", "_").lower()] = int(x[1]) if x[1].isdigit() else x[1]

    nicks = tree.xpath('//*[@id="mobilePartyMembersWrapper"]//div[1]/a/text()')
    member_ids = [int(x.split("?id=")[1]) for x in tree.xpath('//*[@id="mobilePartyMembersWrapper"]//div[1]/a/@href')]
    joined = tree.xpath('//*[@id="mobilePartyMembersWrapper"]//div[2]/i/text()')
    for index, (nick, member_id, joined) in enumerate(zip(nicks, member_ids, joined)):
        icons = tree.xpath(f'//*[@id="mobilePartyMembersWrapper"][{index + 1}]//div[1]//i/@title')
        if icons and "Party Leader" in icons[0]:
            icons[0] = icons[0].replace("Party Leader", "")
            icons.insert(0, "Party Leader")
        row["members_list"].append({"nick": nick.strip(), "id": member_id, "joined": joined, "roles": icons})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/productMarket.html', methods=['GET'])
def productMarket(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    last_page = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href") or ['page=1']
    last_page = int(last_page[0].split('page=')[1])

    products = [x.split("/")[-1].split(".png")[0] for x in
                tree.xpath('//*[@id="productMarketItems"]//tr//td[1]//img[1]/@src')]
    for index, product in enumerate(products):
        quality = tree.xpath(f'//*[@id="productMarketItems"]//tr[{index + 2}]//td[1]//img[2]/@src')
        if "Defense System" in product:
            product = product.replace("Defense System", "Defense_System")
        if quality:
            products[index] = f'{quality[0].split("/")[-1].split(".png")[0].upper()} {product}'

    seller_ids = utils.get_ids_from_path(tree, '//tr//td[2]//a')
    sellers = [x.strip() for x in tree.xpath('//tr//td[2]//a/text()')]
    prices = [float(x) for x in tree.xpath("//tr[position()>1]//td[4]/b/text()")][::2]
    ccs = [x.strip() for x in tree.xpath("//tr[position()>1]//td[4]/text()") if x.strip()][::2]
    stocks = [int(x.strip()) for x in tree.xpath("//tr[position()>1]//td[3]/text()")]
    offer_ids = tree.xpath('//*[@id="command"]/input[1]/@value')
    row = {"pages": last_page, "offers": []}
    for seller_id, seller, product, cc, price, stock, offer_id in zip(seller_ids, sellers, products, ccs, prices,
                                                                      stocks, offer_ids):
        row["offers"].append(
            {"seller": seller, "seller_id": int(seller_id), "product": product, "coin": cc, "price": price,
             "stock": stock, "offer_id": int(offer_id)})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/battlesByWar.html', methods=['GET'])
def battlesByWar(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    last_page = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href") or ['page=1']
    last_page = int(last_page[0].split('page=')[1])
    war = tree.xpath('//*[@name="id"]//option[@selected="selected"]')[0].text.strip()

    sides = [x.replace("xflagsMedium xflagsMedium-", "").replace("-", " ") for x in
             tree.xpath('//*[@id="battlesTable"]//tr//td[1]//div//div//div/@class') if "xflagsMedium" in x]
    defender, attacker = sides[::2], sides[1::2]
    battles_id = [int(x.split("?id=")[1]) for x in tree.xpath('//tr//td[1]//div//div[2]//div[2]/a/@href')]
    battles_region = tree.xpath('//tr//td[1]//div//div[2]//div[2]/a/text()')

    score = tree.xpath('//tr[position()>1]//td[2]/text()')
    dmg = [int(x.replace(",", "").strip()) for x in tree.xpath('//tr[position()>1]//td[3]/text()')]
    battle_start = [x.strip() for x in tree.xpath('//tr[position()>1]//td[4]/text()')]
    row = {"pages": last_page, "war": war, "battles": []}
    for defender, attacker, battle_id, battle_region, score, dmg, battle_start in zip(
            defender, attacker, battles_id, battles_region, score, dmg, battle_start):
        row["battles"].append({"defender_name": defender, "defender_score": int(score.strip().split(":")[0]),
                               "attacker_name": attacker, "attacker_score": int(score.strip().split(":")[1]),
                               "battle_id": battle_id, "dmg": dmg, "region": battle_region,
                               "battle start": battle_start})
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/battles.html', methods=['GET'])
def battles(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    last_page = tree.xpath("//ul[@id='pagination-digg']//li[last()-1]//@href") or ['page=1']
    last_page = int(last_page[0].split('page=')[1])
    country = tree.xpath('//*[@id="countryId"]//option[@selected="selected"]')[0].text
    country_id = int(tree.xpath('//*[@id="countryId"]//option[@selected="selected"]/@value')[0])
    sorting = tree.xpath('//*[@id="sorting"]//option[@selected="selected"]')[0].text.replace("Sort ", "")
    filtering = tree.xpath('//*[@id="filter"]//option[@selected="selected"]')[0].text

    total_dmg = tree.xpath('//*[@class="battleTotalDamage"]/text()')
    progress_attackers = [float(x.replace("%", "")) for x in tree.xpath('//*[@id="attackerScoreInPercent"]/text()')]
    attackers_dmg = tree.xpath('//*[@id="attackerDamage"]/text()')
    defenders_dmg = tree.xpath('//*[@id="defenderDamage"]/text()')
    counters = [i.split(");\n")[0] for i in tree.xpath('//*[@id="battlesTable"]//div//div//script/text()') for i in
                i.split("() + ")[1:]]
    counters = [f'{int(x[0]):02d}:{int(x[1]):02d}:{int(x[2]):02d}' for x in utils.chunker(counters, 3)]
    sides = tree.xpath('//*[@class="battleHeader"]//em/text()')
    battle_ids = tree.xpath('//*[@class="battleHeader"]//a/@href')
    battle_regions = tree.xpath('//*[@class="battleHeader"]//a/text()')
    scores = tree.xpath('//*[@class="battleFooterScore hoverText"]/text()')
    row = {"pages": last_page, "sorting": sorting, "filter": filtering, "country": country, "country_id": country_id,
           "battles": []}
    for i, (dmg, progress_attacker, counter, sides, battle_id, battle_region, score) in enumerate(zip(
            total_dmg, progress_attackers, counters, sides, battle_ids, battle_regions, scores)):
        defender, attacker = sides.split(" vs ")
        row["battles"].append(
            {"total_dmg": dmg, "time_reminding": counter, "battle_id": int(battle_id.split("=")[-1]),
             "region": battle_region,
             "defender": {"name": defender, "score": int(score.strip().split(":")[0]),
                          "bar": round(100 - progress_attacker, 2)},
             "attacker": {"name": attacker, "score": int(score.strip().split(":")[1]),
                          "bar": progress_attacker}})
        if attackers_dmg:
            try:
                row["battles"][-1]["defender"]["dmg"] = int(defenders_dmg[i].replace(",", ""))
                row["battles"][-1]["attacker"]["dmg"] = int(attackers_dmg[i].replace(",", ""))
            except:
                pass
    return utils.prepare_request(row)


@app.route('/<https>://<server>.e-sim.org/profile.html', methods=['GET'])
def profile(https, server):
    tree = utils.get_tree(f"{request.full_path[1:].replace(f'{https}:/', 'https://')}")
    all_parameters = ["avoid", "max", "crit", "damage", "dmg", "miss", "flight", "consume", "eco", "str", "hit",
                      "less", "find", "split", "production", "merging", "restore", "increase"]
    medals_headers = ["congress", "cp", "train", "inviter", "subs", "work", "bh", "rw", "tester", "tournament"]
    friends = ([x.replace("Friends", "").replace("(", "").replace(")", "") for x in
                tree.xpath("//div[@class='rank']/text()") if "Friends" in x] or [0])[0]
    inactive = [int(x.split()[-2]) for x in tree.xpath('//*[@class="profile-data red"]/text()') if
                "This citizen has been inactive for" in x]
    status = "" if not inactive else str(date.today() - timedelta(days=inactive[0]))
    banned_by = [x.strip() for x in tree.xpath('//*[@class="profile-data red"]//div/a/text()')] or [""]
    premium = len(tree.xpath('//*[@class="premium-account"]')) != 0
    birthday = (tree.xpath('//*[@class="profile-row" and span = "Birthday"]/span/text()') or [1])[0]
    debts = sum(float(x) for x in tree.xpath('//*[@class="profile-data red"]//li/text()')[::6])
    assets = sum(float(x.strip()) for x in tree.xpath(
        '//*[@class="profile-data" and (strong = "Assets")]//ul//li/text()') if "\n" in x)
    is_online = tree.xpath('//*[@id="loginBar"]/span[2]/@class')[0] == "online"

    medals = {}
    for i, medal in enumerate(medals_headers, 1):
        medalse_count = tree.xpath(f"//*[@id='medals']//ul//li[{i}]//div//text()")
        if medalse_count:
            medals[medal.lower()] = int(medalse_count[0].replace("x", ""))
        elif "emptyMedal" not in tree.xpath(f"//*[@id='medals']//ul//li[{i}]/img/@src")[0]:
            medals[medal.lower()] = 1
        else:
            medals[medal.lower()] = 0

    buffs_debuffs = [
        utils.camel_case_merge(x.split("/specialItems/")[-1].split(".png")[0]).replace("Elixir", "") for x in
            tree.xpath('//*[@class="profile-row" and (strong="Debuffs" or strong="Buffs")]//img/@src') if
                "//cdn.e-sim.org//img/specialItems/" in x]
    buffs = [x.split("_")[0].replace("Vacations", "Vac").replace("Resistance", "Sewer").replace(
        "Pain Dealer", "PD ").replace("Bonus Damage", "").replace("  ", " ") + (
                 "% Bonus" if "Bonus Damage" in x.split("_")[0] else "")
             for x in buffs_debuffs if "Positive" in x.split("_")[1:]]
    debuffs = [x.split("_")[0].lower().replace("Vacation", "Vac").replace(
        "Resistance", "Sewer").replace("  ", " ") for x in buffs_debuffs if "Negative" in x.split("_")[1:]]

    equipments = []
    for slot_path in tree.xpath('//*[@id="profileEquipmentNew"]//div//div//div//@title'):
        tree = fromstring(slot_path)
        try:
            eq_type = tree.xpath('//b/text()')[0].strip()
        except IndexError:
            continue

        parameters_string = tree.xpath('//p/text()')
        parameters = []
        values = []
        for parameter_string in parameters_string:
            for x in all_parameters:
                if x in parameter_string.lower():
                    parameters.append(x)
                    values.append(float(parameter_string.split(" ")[-1].replace("%", "").strip()))
                    break

        equipments.append(
            {"type": " ".join(eq_type.split()[1:]), "quality": eq_type.split()[0][1], "first_parameter": parameters[0],
             "second_parameter": parameters[1], "third_parameter": parameters[2] if len(parameters) == 3 else "",
             "first_value": values[0], "second_value": values[1], "third_value": values[2] if len(values) == 3 else 0})
    row = {"medals": medals, "friends": int(friends), "equipments": equipments,
           "inactive_days": inactive[0] if inactive else 0,
           "premium": premium, "birthday": birthday, "is_online": is_online,
           "assets": assets, "debts": debts, "buffs": buffs, "debuffs": debuffs}
    if banned_by and banned_by[0]:
        row.update({"banned_by": banned_by[0]})
    if status:
        row.update({"last_login": status})
    return utils.prepare_request(row)


if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
