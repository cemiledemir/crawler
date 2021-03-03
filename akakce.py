# -*- coding: utf-8 -*-
import re
import json
from random import random
from urllib.parse import urljoin

import scrapy

from crawlms.utils import get_urlparam, parse_datetime, parse_price, parse_shipping_cost

from ..items import OfferItem


class AkakceSpider(scrapy.Spider):
    name = "akakce"
    allowed_domains = ["www.akakce.com"]
    start_urls = [
        "https://www.akakce.com/cep-telefonu/en-ucuz-xiaomi-redmi-note-8-64gb-fiyati,518572988.html"
    ]

    def parse(self, response):
        offers = self._extract_offers(response)
        load_more_url = response.css("script::text").re_first(
            r"BoostSAPB\('SAP','([^']*)"
        )
        if not load_more_url:
            return offers
        if offers[0]["link"] == "variant":
            return offers
        url = f"/j/pl/?{load_more_url}&{random()}"
        # Защита эндпойнта ожидает GET-запрос c заголовком POST-запроса, оступился -- бан.
        # Может давать 404 при неверном user-agent.
        headers = {"Content-type": "application/x-www-form-urlencoded;charset=utf-8"}
        return [
            response.follow(
                url, self.parse_more, headers=headers, meta=dict(offers=offers)
            )
        ]

    def parse_more(self, response):
        offers = response.meta["offers"]
        offers.extend(self._extract_offers(response))
        return offers

    @staticmethod
    def _extract_offers(response):
        offers = []
        if (
            "fiyati" not in response.request.url
            and "j/pl/?p=" not in response.request.url
            and "arama" not in response.request.url
        ):
            offer = OfferItem()
            offer["link"] = None
            offer["shipping_cost"] = None
            offers.append(offer)

        elif "arama" in response.request.url:
            data = response.css("script").re_first(r"var QVC = (.*);")
            # Regex used to make json object valid
            spl = data.split(", QVC")[0]
            for i in set(
                re.findall(r'(?:[a-z]+(?=:[" ]))', spl)
            ):  # double quotes the keys
                spl = spl.replace(f"{i}:", f'"{i}":')
            for j in set(
                re.findall(r"(?:[\d]+(?=:\[))", spl)
            ):  # double quotes the product ids
                spl = spl.replace(f"{j}:", f'"{j}":')
            spl = re.sub(r"(?:,+(?=\}))", "", spl)  # gets rid of unnecessary commas
            spl2 = json.loads(spl)
            for key, value in spl2.items():
                if (
                    response.css(f'li[data-pr="{key}"] a').xpath("@href").get()
                    is not None
                ):  # if redirect to akakçe
                    if (
                        "fiyati"
                        in response.css(f'li[data-pr="{key}"] a').xpath("@href").get()
                    ):
                        offer = OfferItem()
                        offer["link"] = None
                        offer["shipping_cost"] = None
                        offers.append(offer)
                    break
                else:
                    if (
                        len(spl2) == 1
                    ):  # if 1 product is listed, the products are scraped
                        for k in value:
                            if "s" in k.keys():
                                offer = OfferItem()
                                p = "".join(list(k.values())[0])
                                s = "".join(list(k.values())[1])
                                u = "".join(list(k.values())[2])
                                offer["title"] = (
                                    response.xpath(f"//li[contains(@data-pr, '{key}')]")
                                    .css("h3::text")[0]
                                    .extract()
                                )
                                c = u.replace(re.findall(r"\#/.*?\/", u)[0], "/c/")
                                url = c.split("&amp;")[0]
                                for i in range(1, len(c.split("&amp;"))):
                                    url += "&" + c.split("&amp;")[i]
                                offer["link"] = _unwrap_url(url)
                                offer["price"] = parse_price(p + "TL")
                                if s == "0,00":
                                    offer["shipping_cost"] = parse_shipping_cost(
                                        "Ücretsiz kargo"
                                    )
                                else:
                                    offer["shipping_cost"] = parse_shipping_cost(
                                        "+" + s + "TL kargo"
                                    )
                                offer["last_updated_at"] = parse_datetime(
                                    None, settings={"TIMEZONE": "+0300"}
                                )
                                offers.append(offer)
                    else:  # if more than one product is listed the error is not found
                        offer = OfferItem()
                        offer["link"] = None
                        offer["shipping_cost"] = None
                        offers.append(offer)
        else:
            if response.xpath("//div[@id='PL404_C']/h2/text()").get() is None:
                variant_type = [
                    span.css("span.prv_v8 > b::text").get()
                    for span in response.css(".pd_v8 > span")
                ]
                if (
                    "Renk seçenekleri:" in variant_type
                ):  # check if there are color variants if response.css('#PRV_v8')
                    variant_links = [
                        _create_url(li.css("a::attr(href)").get())
                        for li in response.css("#PRV_v8 > li")
                    ]
                    try:
                        variant_color = (
                            response.xpath("//*[@class='prvbm_v8']/b/text()")
                            .get()
                            .translate(str.maketrans("ğĞıİöÖüÜşŞçÇ", "gGiIoOuUsScC"))
                            .lower()
                        )
                    except:
                        variants = [
                            li.css("a > img::attr(alt)")
                            .get()
                            .translate(str.maketrans("ğĞıİöÖüÜşŞçÇ", "gGiIoOuUsScC"))
                            .lower()
                            .replace(" ", "-")
                            for li in response.css("#PRV_v8 > li")
                        ]
                        if (
                            any(v in response.request.url for v in variants)
                            or response.request.url in variant_links
                        ):
                            variant_color = "".join(
                                [v for v in variants if v in response.request.url]
                            )
                            count = 0
                            for li in response.css("ul.pl_v8 > li"):
                                store = li.css("a > span > span > img::attr(alt)").get()
                                if store is None:
                                    store = li.css("a > span > span::text").get()
                                if "Hepsiburada" in store:
                                    offers.append(
                                        crawl_product(
                                            li,
                                            variant_color.replace("-", " "),
                                            variant_links,
                                        )
                                    )
                            for li in response.css("ul.pl_v8 > li"):
                                store = li.css("a > span > span > img::attr(alt)").get()
                                if store is None:
                                    store = li.css("a > span > span::text").get()
                                if "Hepsiburada" not in store:
                                    count += 1
                                    offers.append(
                                        crawl_product(
                                            li,
                                            variant_color.replace("-", " "),
                                            variant_links,
                                        )
                                    )
                                    if count == 10:
                                        break
                            if not offers:
                                offers.append(
                                    single_product(
                                        response,
                                        variant_color.replace("-", " "),
                                        variant_links,
                                    )
                                )
                        else:
                            offer = OfferItem()
                            offer["link"] = "variant"
                            offer["shipping_cost"] = None
                            offer["variant_link"] = variant_links
                            offers.append(offer)
                    else:
                        if (
                            variant_color.replace(" ", "-") in response.request.url
                            or response.request.url in variant_links
                        ):
                            # variant_color = ''.join([v for v in variants if v in response.request.url])
                            count = 0
                            for li in response.css("ul.pl_v8 > li"):
                                store = li.css("a > span > span > img::attr(alt)").get()
                                if store is None:
                                    store = li.css("a > span > span::text").get()
                                if "Hepsiburada" in store:
                                    offers.append(
                                        crawl_product(
                                            li,
                                            variant_color.replace("-", " "),
                                            variant_links,
                                        )
                                    )
                            for li in response.css("ul.pl_v8 > li"):
                                store = li.css("a > span > span > img::attr(alt)").get()
                                if store is None:
                                    store = li.css("a > span > span::text").get()
                                if "Hepsiburada" not in store:
                                    count += 1
                                    offers.append(
                                        crawl_product(
                                            li,
                                            variant_color.replace("-", " "),
                                            variant_links,
                                        )
                                    )
                                    if count == 10:
                                        break
                            if not offers:
                                offers.append(
                                    single_product(
                                        response,
                                        variant_color.replace("-", " "),
                                        variant_links,
                                    )
                                )
                        else:
                            offer = OfferItem()
                            offer["link"] = "variant"
                            offer["shipping_cost"] = None
                            offer["variant_link"] = variant_links
                            offers.append(offer)
                else:
                    count = 0
                    print(response.css("#PL > li").get())
                    for li in response.css("ul.pl_v8 > li"):
                        store = li.css("a > span > span > img::attr(alt)").get()
                        if store is None:
                            store = li.css("a > span > span::text").get()
                        if "Hepsiburada" in store:
                            offers.append(crawl_product(li, "-", "-"))
                    for li in response.css("ul.pl_v8 > li"):
                        store = li.css("a > span > span > img::attr(alt)").get()
                        if store is None:
                            store = li.css("a > span > span::text").get()
                        if "Hepsiburada" not in store:
                            count += 1
                            offers.append(crawl_product(li, "-", "-"))
                            if count == 10:
                                break
                    if not offers:
                        offers.append(single_product(response, "-", "-"))
            else:
                offer = OfferItem()
                offer["link"] = None
                offer["shipping_cost"] = None
                offers.append(offer)
        return offers


def crawl_product(li, color, link):
    offer = OfferItem()
    offer["title"] = li.css("h3::text").get()
    offer["link"] = _unwrap_url(li.css("a::attr(href)").get())
    offer["price"] = parse_price("".join(li.css("span.pt_v8 ::text").getall()))
    offer["shipping_cost"] = parse_shipping_cost(li.css("span.pt_v8 + em::text").get())
    offer["last_updated_at"] = parse_datetime(
        li.css("span.bd_v8 > i::text").get(), settings={"TIMEZONE": "+0300"}
    )
    offer["variant_color"] = color
    offer["variant_link"] = link
    return offer


def single_product(r, color, link):
    offer = OfferItem()
    try:
        offer["title"] = r.css("h1::text").get()
    except Exception as e:
        offer["title"] = "None"
    try:
        offer["link"] = _unwrap_url(r.css("div.bb_w a").xpath("@href").get())
    except Exception as e:
        offer["link"] = ""
    if offer["link"] == "":
        offer["title"] = "None"
        offer["shipping_cost"] = None
        offer["variant_color"] = color
        offer["variant_link"] = link
    else:
        offer["price"] = parse_price("".join(r.css("span.pt_v8 ::text").getall()))
        offer["shipping_cost"] = parse_shipping_cost(
            r.css("span.pt_v8 + em::text").get()
        )
        offer["last_updated_at"] = parse_datetime(
            r.css("span.bd_v8 > i::text").get(), settings={"TIMEZONE": "+0300"}
        )
        offer["variant_color"] = color
        offer["variant_link"] = link
    return offer


def _create_url(url):
    return urljoin("https://www.akakce.com/", url)


def _unwrap_url(url):
    return get_urlparam(get_urlparam(url[1:], "f"), "r")
