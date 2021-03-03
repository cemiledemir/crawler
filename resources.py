# -*- coding: utf-8 -*-
import re
import csv
import string
import itertools
from collections import Counter
import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse, quote, unquote

from crawlms.resource_utils import translate, clean_title, no_parameters, parameters
from crawlms.singularization_helper_objects import matching_obj, checking_obj

from scrapyrt.resources import CrawlResource
from twisted.internet import defer
from crawlms.scrapyrt.resources import MultiCrawlResource
from crawlms.utils import get_first, safe_cast

# from scrapyrt import log
# from scrapyrt.utils import extract_scrapy_request_args, to_bytes


class SentryHealthCheckResource(MultiCrawlResource):
    def render_GET(self, request, **kwargs):
        division_by_zero = 1 / 0
        print(f"sentry error should have been sent! {division_by_zero}")


# pylint: disable=abstract-method
class PickTopResource(MultiCrawlResource):
    def render_GET(self, request, **kwargs):
        try:
            dfd = super().render_GET(request, **kwargs)
            m = request.args.get(b"model")
            var = get_first(request.args.get(b"variant", [None]))
            limit = safe_cast(get_first(request.args.get(b"limit", [])), int)
            top = safe_cast(get_first(request.args.get(b"top", [])), int)
            dfd.addCallback(self.pick_top, limit=limit, top=top, model=m, var=var)
            self.link = request.args.get(b"url")
            return dfd
        except Exception as e:
            logging.info(
                f"Pick Top end pointi hata aldi! render_GET fonksiyonu: {str(e)}"
            )

    def pick_top(self, data, limit=None, top=None, model=None, var=None):
        global variant, hepsiburada, offers, times
        errors = []
        color = [
            r["items"][0]["variant_color"]
            for r in data
            if len(r["items"]) > 0
            if "variant_color" in r["items"][0]
        ]
        if len(color) == 2 and (
            "-" in color
            or [i for i in color[0].split() if i in color[1]]
            or [i for i in color[1].split() if i in color[0]]
        ):
            if list(set(color)) == ["-"]:
                offers = self.return_offer(data, limit, top)
                errors, times, hepsiburada = self.pick_top_outputs(data, limit, top)
            else:
                variant_data = []
                for i in [
                    r["spider_name"]
                    for r in data
                    if len(r["items"]) > 0
                    if "variant_color" in r["items"][0]
                    if r["items"][0]["variant_color"] != "-"
                ]:
                    variant_data += [d for d in data if d.get("spider_name") == i]
                non_variant = [x for x in data if x not in variant_data]
                links = [
                    i["link"].split("&")[0] for r in variant_data for i in r["items"]
                ]
                non_variant_links = [
                    i["link"].split("&")[0] for r in non_variant for i in r["items"]
                ]
                shared_links = [
                    s["link"].split("&")[0]
                    for d in non_variant
                    for s in d["items"]
                    if s["link"].split("&")[0]
                    in [z for z in links if z in non_variant_links]
                ]
                include = [
                    {f"{d['spider_name']}": s}
                    for d in non_variant
                    for s in d["items"]
                    if s["link"].split("&")[0] in shared_links
                ]
                exclude = [
                    {f"{d['spider_name']}": s}
                    for d in non_variant
                    for s in d["items"]
                    if s["link"].split("&")[0] not in shared_links
                ]
                if "-" in color:
                    color.remove("-")
                include += [
                    {key: value}
                    for i in exclude
                    for key, value in i.items()
                    for c in color
                    if "title" in value.keys()
                    if c in translate(value["title"])
                ]
                include += [
                    {key: value}
                    for i in exclude
                    for key, value in i.items()
                    for c in color
                    if "epey_color" in value.keys()
                    if value["epey_color"] is not None
                    if c in translate(value["epey_color"])
                ]
                non_variants = non_variant.copy()
                for i in non_variants:
                    i["items"] = []
                for j in non_variants:
                    j["items"] = [
                        value
                        for i in include
                        for key, value in i.items()
                        if key == j["spider_name"]
                    ]
                variant_data += non_variants
                offers = self.return_offer(variant_data, limit, top)
                errors, times, hepsiburada = self.pick_top_outputs(
                    variant_data, limit, top
                )
        elif len(color) == 2 and any(x == color[0] for x in color):
            try:
                hb_akakce = [
                    quote(i["link"], safe="://%")
                    for r in data
                    for i in r["items"]
                    if r["spider_name"] == "akakce"
                    if len(r["items"]) > 0
                    if "hepsiburada" in i["link"]
                ]
                hb_cimri = [
                    quote(i["link"], safe="://%")
                    for r in data
                    for i in r["items"]
                    if r["spider_name"] == "cimri"
                    if len(r["items"]) > 0
                    if "hepsiburada" in i["link"]
                ]
            except:
                links = [
                    self.link[i].decode("latin1")
                    for i in range(len(self.link))
                    if any(
                        c in self.link[i].decode("latin1") for c in ("akakce", "cimri")
                    )
                ]
                error = {
                    "comparison_website": "akakce & cimri",
                    "reason": "The variants of the links you want to add are different from each other.",
                    "links": tuple(links),
                }
                errors.append(error)
            else:
                if not [i for i in hb_akakce if i in hb_cimri]:
                    links = [
                        self.link[i].decode("latin1")
                        for i in range(len(self.link))
                        if any(
                            c in self.link[i].decode("latin1")
                            for c in ("akakce", "cimri")
                        )
                    ]
                    error = {
                        "comparison_website": "akakce & cimri",
                        "reason": "The variants of the links you want to add are different from each other.",
                        "links": tuple(links),
                    }
                    errors.append(error)
                else:
                    variant_data = []
                    for i in [
                        r["spider_name"]
                        for r in data
                        if len(r["items"]) > 0
                        if "variant_color" in r["items"][0]
                        if r["items"][0]["variant_color"] != "-"
                    ]:
                        variant_data += [d for d in data if d.get("spider_name") == i]
                    non_variant = [x for x in data if x not in variant_data]
                    links = [
                        i["link"].split("&")[0]
                        for r in variant_data
                        for i in r["items"]
                    ]
                    non_variant_links = [
                        i["link"].split("&")[0] for r in non_variant for i in r["items"]
                    ]
                    shared_links = [
                        s["link"].split("&")[0]
                        for d in non_variant
                        for s in d["items"]
                        if s["link"].split("&")[0]
                        in [z for z in links if z in non_variant_links]
                    ]
                    include = [
                        {f"{d['spider_name']}": s}
                        for d in non_variant
                        for s in d["items"]
                        if s["link"].split("&")[0] in shared_links
                    ]
                    exclude = [
                        {f"{d['spider_name']}": s}
                        for d in non_variant
                        for s in d["items"]
                        if s["link"].split("&")[0] not in shared_links
                    ]
                    if "-" in color:
                        color.remove("-")
                    include += [
                        {key: value}
                        for i in exclude
                        for key, value in i.items()
                        for c in color
                        if "title" in value.keys()
                        if c in translate(value["title"])
                    ]
                    include += [
                        {key: value}
                        for i in exclude
                        for key, value in i.items()
                        for c in color
                        if "epey_color" in value.keys()
                        if value["epey_color"] is not None
                        if c in translate(value["epey_color"])
                    ]
                    non_variants = non_variant.copy()
                    for i in non_variants:
                        i["items"] = []
                    for j in non_variants:
                        j["items"] = [
                            value
                            for i in include
                            for key, value in i.items()
                            if key == j["spider_name"]
                        ]
                    variant_data += non_variants
                    offers = self.return_offer(variant_data, limit, top)
                    errors, times, hepsiburada = self.pick_top_outputs(
                        variant_data, limit, top
                    )
        elif len(data) != 1 and len(color) == 1 and "-" not in color:
            name = [
                r["spider_name"]
                for r in data
                if len(r["items"]) > 0
                if "variant_color" in r["items"][0]
                if r["items"][0]["variant_color"] != "-"
            ]
            variant_data = [d for d in data if d.get("spider_name") == name[0]]
            epey = [d for d in data if d.get("spider_name") == "epey"]
            if epey:
                links = [
                    self._clean_url(i["link"]).split("&")[0]
                    for r in variant_data
                    for i in r["items"]
                ]
                non_variant_links = [
                    self._clean_url(i["link"]).split("&")[0]
                    for r in epey
                    for i in r["items"]
                ]
                shared_links = [
                    self._clean_url(s["link"]).split("&")[0]
                    for d in epey
                    for s in d["items"]
                    if self._clean_url(s["link"]).split("&")[0]
                    in [z for z in links if z in non_variant_links]
                ]
                include = [
                    s
                    for d in epey
                    for s in d["items"]
                    if self._clean_url(s["link"]).split("&")[0] in shared_links
                ]
                exclude = [
                    s
                    for d in epey
                    for s in d["items"]
                    if self._clean_url(s["link"]).split("&")[0] not in shared_links
                ]
                include += [
                    i
                    for i in exclude
                    if "title" in i
                    if color[0] in translate(i["title"])
                ]
                include += [
                    i
                    for i in exclude
                    if "epey_color" in i
                    if i["epey_color"] is not None
                    if color[0] in translate(i["epey_color"])
                ]
                epey[0]["items"] = include
                variant_data += epey
                offers = self.return_offer(variant_data, limit, top)  # variant_data
                errors, times, hepsiburada = self.pick_top_outputs(
                    variant_data, limit, top
                )
            else:
                offers = self.return_offer(data, limit, top)
                errors, times, hepsiburada = self.pick_top_outputs(data, limit, top)
        elif (
            len(data[0]["items"]) > 0
            and data[0]["items"][0]["link"] == "variant"
            and not color
        ):
            pass
        else:
            offers = self.return_offer(data, limit, top)  # data
            errors, times, hepsiburada = self.pick_top_outputs(data, limit, top)

        variants = []
        for r in data:
            if len(r["items"]) > 0:
                if "variant_link" in r["items"][0]:
                    if r["items"][0]["variant_link"] != "-":
                        variant = {
                            "comparison_website": r["spider_name"],
                            "variant_urls": tuple(r["items"][0]["variant_link"]),
                        }
                        variants.append(variant)
        k = [x["hb_id"] for x in hepsiburada if "hb_id" in x.keys()]
        hb = []
        for i in Counter(k):
            all = [x for x in hepsiburada if x["hb_id"] == i]
            hb.append(max(all, key=lambda x: x["title"]))

        # -------------------------------------- CREATE PARAMETERS -------------------------------------------
        colors = []
        with open("colors.csv", "r") as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                color = translate(row[0])
                colors.append(color)
        blocks = []
        with open("stopwords.csv", "r") as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                words = translate(row[0])
                blocks.append(words)

        def differences(first, second, trace=None):
            unique = set(first.split()).symmetric_difference(set(second.split()))
            uniques = [
                x
                for x in list(unique)
                if not (x.isdigit() or x[0] == "-" and x[1:].isdigit())
            ]
            if uniques:
                for substring in uniques:
                    u = uniques.copy()
                    u.remove(substring)
                    if any(substring in s for s in u):
                        uniques.remove(substring)
                uniques = [s for s in uniques if len(s) != 1]
                data = checking_obj
                data = preprocess_json(data)
                for key, value in data:
                    if translate(key) and translate(value) in uniques:
                        pass
                    else:
                        u = uniques.copy()
                        for elem in u:
                            if elem in blocks:
                                uniques.remove(elem)
                u = uniques.copy()
                for i in u:
                    if i in colors or i in string.punctuation:
                        uniques.remove(i)
                if "yurt" in uniques:
                    uniques[0] = "yurt"
                if trace is not None:
                    uniques.remove(trace)
                if uniques:
                    return uniques[0]

        def match_words(match_file, title):
            get_title = clean_title(title)
            for key, value in match_file:
                if translate(key) in get_title:
                    get_title = get_title.replace(translate(key), translate(value))
            return get_title

        if len(hb) > 1:
            data = matching_obj
            data = preprocess_json(data)
            titles = []
            hb_ids = []
            for i in hb:
                titles.append(match_words(data, i.get("title")))
                hb_ids.append(i.get("hb_id"))
            combinations = itertools.combinations(titles, 2)
            alls = []
            for first, second in combinations:
                diff = differences(first, second)
                if diff in alls:
                    alls.append(differences(first, second, trace=diff))
                else:
                    alls.append(diff)
            for i in hb:
                i["params"] = {}
                t = (
                    clean_title(i.get("title"))
                )
                l = (
                    i.get("link")
                    .split("?")[0]
                )
                for color in colors:
                    if color in t or color.replace(" ", "-") in l:
                        i["params"]["variant"] = color.replace(" ", "-")
                        break
                i["params"]["model"] = []
                for j in alls:
                    if j is not None:
                        if j not in colors:
                            if j == "ram":
                                if j in i.get("link").lower() or j in clean_title(
                                    i.get("title")
                                ):
                                    print(i.get("link").lower())
                                    index = i.get("link").split("-").index(j)
                                    ram = f'{i.get("link").split("-")[index - 2]}-{i.get("link").split("-")[index - 1]}-{i.get("link").split("-")[index]}'
                                    i["params"]["model"].append(ram)
                                else:
                                    i["params"]["model"].append(f"not-{j}")
                            if j != "ram":
                                if j in translate(
                                    i.get("link")
                                ).lower() or j in clean_title(i.get("title")):
                                    i["params"]["model"].append(j)
                                else:
                                    i["params"]["model"].append(f"not-{j}")

        if not hb:
            hb = hepsiburada
        # ---------------------- CHECK FOR PARAMETERS ---------------------------------------
        dual = [b"sim", b"dual", b"duos"]
        dist = [b"distributor", b"turkiye"]
        # vars = {"coral": "mercan",

        if model is not None:
            for m in model:
                if "not" not in m.decode("utf-8"):
                    if m in dual:
                        offer = offers.copy()
                        offers = parameters(offers, m)
                        hb = parameters(hb, m)
                        for d in dual:
                            offers.extend(parameters(offer, d))
                    if m in dist:
                        offer = offers.copy()
                        offers = parameters(offers, m)
                        hb = parameters(hb, m)
                        for d in dist:
                            offers.extend(parameters(offer, d))
                    else:
                        offers = parameters(offers, m)
                        hb = parameters(hb, m)
                if "not" in m.decode("utf-8"):
                    model = re.sub("not-", "", m.decode("utf-8"))
                    offers = no_parameters(offers, model)
                    hb = no_parameters(hb, model)
        if var is not None:
            offers = parameters(offers, var)
            hb = parameters(hb, var)

        if model or var is not None:
            for i in hb:
                i["other_ids"] = hb_ids

        return (
            {"product": offers},
            {"variant_urls": [dict(e) for e in {tuple(d.items()) for d in variants}]},
            {"error": [dict(e) for e in {tuple(d.items()) for d in errors}]},
            {"time": [dict(t) for t in {tuple(d.items()) for d in times}]},
            {"hepsiburada": hb},
        )

    def return_offer(self, data, limit=None, top=None):
        offers2 = (
            {
                **offer,
                "link": self._enrich_url(self._clean_url(offer["link"])),
                "comparsion_website": r["spider_name"],
                "total_price": round(offer["price"] + offer["shipping_cost"], 2),
            }
            for r in data
            for offer in r["items"]
            if offer["shipping_cost"] is not None
            and not self._should_be_excluded(offer["link"])
        )
        offers2 = sorted(
            offers2, key=lambda offer: offer["last_updated_at"], reverse=True
        )
        offers2 = offers2[:limit]
        offers2 = sorted(offers2, key=lambda offer: offer["total_price"])
        offers2 = offers2[:top]
        for i in offers2:
            if "variant_link" in i.keys():
                del i["variant_link"]
        return offers2

    def pick_top_outputs(self, data, limit=None, top=None):
        print(data)
        errors = []
        times = []
        hepsiburada = []
        links = ""
        hb_products = (
            {
                **offer,
                "link": self._enrich_url(self._clean_url(offer["link"])),
                "comparsion_website": r["spider_name"],
                "total_price": round(offer["price"] + offer["shipping_cost"], 2),
            }
            if offer["shipping_cost"] is not None
            else {
                **offer,
                "link": self._enrich_url(self._clean_url(offer["link"])),
                "comparsion_website": r["spider_name"],
                "total_price": round(offer["price"], 2),
            }
            if offer["shipping_cost"] is None
            else {}
            for r in data
            for offer in r["items"]
            if not self._should_be_excluded(offer["link"])
            and "hepsiburada" in offer["link"]
        )
        hb_products = sorted(
            hb_products, key=lambda hb: hb["last_updated_at"], reverse=True
        )
        hb_products = hb_products[:limit]
        hb_products = sorted(hb_products, key=lambda hb: hb["total_price"])
        hb_products = hb_products[:top]
        for i in hb_products:
            hb_id = self.parse_hb_id(i["link"])
            hepsi_burada = {
                "title": i["title"],
                "link": i["link"],
                "hb_id": hb_id,
            }
            hepsiburada.append(hepsi_burada)
        for r in data:
            for offer in r["items"]:
                if offer["link"] is not None:
                    links += self._enrich_url(self._clean_url(offer["link"]))
            links += links
            continue
        if "hepsiburada" not in links and links != "":
            link = []
            for i in range(len(self.link)):
                link.append(self.link[i].decode("latin1"))
            hepsi_burada = {
                "comparison_website": "all",
                "error": "No Hepsiburada Product",
                "links": tuple(link),
            }
            hepsiburada.append(dict(hepsi_burada))
        for r in data:
            execution_time = r["stats"]["elapsed_time_seconds"]
            for offer in r["items"]:
                for i in range(len(self.link)):
                    if r["spider_name"] in self.link[i].decode("latin1"):
                        time = {
                            "comparison_website": r["spider_name"],
                            "execution_time": execution_time,
                            "link": self.link[i].decode("latin1"),
                        }
                        times.append(time)
                    if offer["link"] == "":
                        if r["spider_name"] in self.link[i].decode("latin1"):
                            offers2 = {
                                "comparison_website": r["spider_name"],
                                "reason": "No Product",
                                "link": self.link[i].decode("latin1"),
                            }
                            errors.append(offers2)
                    elif offer["link"] is None:
                        if r["spider_name"] in self.link[i].decode("latin1"):
                            offers2 = {
                                "comparison_website": r["spider_name"],
                                "reason": "Not Found",
                                "link": self.link[i].decode("latin1"),
                            }
                            errors.append(offers2)
                    elif offer["link"] == "variant":
                        if r["spider_name"] in self.link[i].decode("latin1"):
                            offers2 = {
                                "comparison_website": r["spider_name"],
                                "reason": "The product can't be added because the variant is not selected.",
                                "link": self.link[i].decode("latin1"),
                            }
                            errors.append(offers2)
            for i in r["stats"]:
                if "httperror/response_ignored_status_count" in i:
                    for j in range(len(self.link)):
                        if r["spider_name"] in self.link[j].decode("latin1"):
                            error = {
                                "comparison_website": r["spider_name"],
                                "reason": f"{i[-3:]} HTTP Error",
                                "link": self.link[j].decode("latin1"),
                            }
                            errors.append(error)
        return errors, times, hepsiburada

    @staticmethod
    def parse_hb_id(link): #her bir methodu başka bir scriptten çağır burası çok doldu
        left_side = link.split("?")[0]
        right_side = left_side.split("p-")[-1]
        return right_side

    @staticmethod
    def _should_be_excluded(url):
        if not url:
            return True
        hostname = urlparse(url).netloc.split(":")[0]
        if not hostname:  # relative links
            return True
        if hostname in ("example.com", "www.example.com"):
            return True
        return False

    @staticmethod
    def _clean_url(url):
        urlparts = urlparse(url)
        if urlparts.query == "":
            params = parse_qsl(urlparts.fragment)
            params = [
                p
                for p in params
                if not (
                    p[0].startswith("utm_")
                    or p[0]
                    in ("tag", "creative", "creativeASIN", "linkCode", "wt_pc", "ref")
                    or p[0].startswith("adjust_")
                )
            ]
            fragment = urlencode(params)
            urlparts = urlparts._replace(fragment=fragment)
        else:
            params = parse_qsl(urlparts.query)
            params = [
                p
                for p in params
                if not (
                    p[0].startswith("utm_")
                    or p[0]
                    in ("tag", "creative", "creativeASIN", "linkCode", "wt_pc", "ref")
                    or p[0].startswith("adjust_")
                )
            ]
            query = urlencode(params)
            urlparts = urlparts._replace(query=query)
        return urlunparse(urlparts)

    @staticmethod
    def _enrich_url(url):
        urlparts = urlparse(url)
        params = parse_qsl(urlparts.query)
        markets = {
            "www.gittigidiyor.com": {
                "utm_source": "pandme",
                "utm_medium": "ocs",
                "utm_campaign": "cps",
            },
            "www.ciceksepeti.com": {
                "utm_source": "pandme",
                "utm_medium": "oneri",
                "utm_campaign": "marketplace",
            },
            "www.hepsiburada.com": {
                "utm_source": "affiliate",
                "utm_medium": "go",
                "utm_campaign": "cpa",
                "utm_content": "{27359}",
                "utm_term": "kategori-genel",
                "wt_af": "go.{27359}.kategori-genel.cpa",
            },
            "www.n11.com": {
                "utm_source": "aff_go",
                "pfx": "{transaction_id}",
                "utm_medium": "cpc",
                "utm_campaign": "ana-sayfa",
                "utm_term": "{27359}",
            },
        }
        marketplaces = [w for w in markets]
        if urlparts.netloc in marketplaces:
            for utm, param in markets[urlparts.netloc].items():
                params.append((utm, param))
        else:
            params.append(("utm_source", "comp_priceandme"))
            params.append(("utm_medium", "cpc"))
        query = urlencode(params)
        unquote_query = unquote(query)
        urlparts = urlparts._replace(query=unquote_query)
        return urlunparse(urlparts)


class PriceSegmentResource(CrawlResource):
    allowedMethods = ["GET"]

    def render_GET(self, request, **kwargs):
        request.args[b"spider_name"] = [b"hepsiburada"]
        request.args[b"start_requests"] = [b"true"]
        # TODO check if query supplied to api
        query = get_first(request.args.get(b"query", None))
        kwargs["query"] = query.decode("utf-8")
        return super().render_GET(request, **kwargs)

    def render_POST(self, request, **kwargs):
        raise NotImplementedError


class PriceSegmentV2Resource(CrawlResource):
    allowedMethods = ["GET"]

    def render_GET(self, request, **kwargs):
        request.args[b"spider_name"] = [b"hepsiburada_v2"]
        request.args[b"start_requests"] = [b"true"]
        # TODO check if query supplied to api
        query = get_first(request.args.get(b"query", None))
        kwargs["query"] = query.decode("utf-8")
        return super().render_GET(request, **kwargs)

    def render_POST(self, request, **kwargs):
        raise NotImplementedError


class HepsiburadaAllResource(CrawlResource):
    allowedMethods = ["GET"]

    def render_GET(self, request, **kwargs):
        request.args[b"spider_name"] = [b"hepsiburada_all"]
        request.args[b"start_requests"] = [b"true"]
        query = get_first(request.args.get(b"sku", None))
        query = b"https://www.hepsiburada.com/pandme-p-" + query
        kwargs["sku"] = query.decode("utf-8")
        dfd = super().render_GET(request, **kwargs)
        dfd.addCallback(self.pick_product)
        return dfd

    @staticmethod
    def pick_product(data):
        return (data.get("items")[0]).get("product")

    def render_POST(self, request, **kwargs):
        raise NotImplementedError


class EpeyAttributeResource(CrawlResource):
    allowedMethods = ["GET"]

    def render_GET(self, request, **kwargs):
        request.args[b"spider_name"] = [b"epey_attribute"]
        request.args[b"start_requests"] = [b"true"]
        query = get_first(request.args.get(b"url", None))
        kwargs["url"] = query.decode("utf-8")
        dfd = super().render_GET(request, **kwargs)
        dfd.addCallback(self.pick_product)
        return dfd

    @staticmethod
    def pick_product(data):
        return data.get("items")[0]

    def render_POST(self, request, **kwargs):
        raise NotImplementedError


class BenchmarkScoresResource(CrawlResource):
    allowedMethods = ["GET"]

    def render_GET(self, request, **kwargs):
        query = get_first(request.args.get(b"url", None)).decode("utf-8")
        for i in range(1, len(list(request.args.keys()))):
            query += f"&{list(request.args.keys())[i].decode('utf-8')}={list(request.args.values())[i][0].decode('utf-8')}"
        request.args[b"spider_name"] = [b"benchmark_scores"]
        request.args[b"start_requests"] = [b"true"]
        kwargs["url"] = query
        dfd = super().render_GET(request, **kwargs)
        dfd.addCallback(self.pick_product)
        return dfd

    @staticmethod
    def pick_product(data):
        return data.get("items")[0]

    def render_POST(self, request, **kwargs):
        raise NotImplementedError


class KimovilScoresResource(CrawlResource):
    allowedMethods = ["GET"]

    def render_GET(self, request, **kwargs):
        request.args[b"spider_name"] = [b"kimovil_scores"]
        request.args[b"start_requests"] = [b"true"]
        query = get_first(request.args.get(b"url", None))
        kwargs["url"] = query.decode("utf-8")
        dfd = super().render_GET(request, **kwargs)
        dfd.addCallback(self.pick_product)
        return dfd

    @staticmethod
    def pick_product(data):
        return data.get("items")[0]

    def render_POST(self, request, **kwargs):
        raise NotImplementedError


class KimovilLinksResource(CrawlResource):
    allowedMethods = ["GET"]

    def render_GET(self, request, **kwargs):
        request.args[b"spider_name"] = [b"kimovil_links"]
        request.args[b"start_requests"] = [b"true"]
        query = get_first(request.args.get(b"url", None))
        kwargs["url"] = query.decode("utf-8")
        dfd = super().render_GET(request, **kwargs)
        dfd.addCallback(self.pick_product)
        return dfd

    @staticmethod
    def pick_product(data):
        return data.get("items")[0]

    def render_POST(self, request, **kwargs):
        raise NotImplementedError


class TechnicalCityScoresResource(CrawlResource):
    allowedMethods = ["GET"]

    def render_GET(self, request, **kwargs):
        request.args[b"spider_name"] = [b"technical_scores"]
        request.args[b"start_requests"] = [b"true"]
        query = get_first(request.args.get(b"url", None))
        kwargs["url"] = query.decode("utf-8")
        dfd = super().render_GET(request, **kwargs)
        dfd.addCallback(self.pick_product)
        return dfd

    @staticmethod
    def pick_product(data):
        return data.get("items")


def render_POST(self, request, **kwargs):
    raise NotImplementedError


class PingResource(CrawlResource):
    allowedMethods = ["GET"]

    def render_GET(self, request, **kwargs):
        return defer.succeed({})
