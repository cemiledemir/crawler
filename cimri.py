# -*- coding: utf-8 -*-
import itertools
import json
import csv
from datetime import datetime
from urllib.parse import urljoin
import scrapy

from ..items import OfferItem


class CimriSpider(scrapy.Spider):
    name = "cimri"
    allowed_domains = ["www.cimri.com"]
    start_urls = [
        "https://www.cimri.com/cep-telefonlari/en-ucuz-xiaomi-redmi-note-8-64gb-4gb-ram-6-3-inc-48mp-akilli-cep-telefonu-mavi-fiyatlari,330907466"
    ]

    def parse(self, response):
        return self._extract_offers(response)

    @staticmethod
    def _extract_offers(response):
        colors = []
        with open("colors.csv", "r") as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                colors.append(
                    row[0]
                    .translate(str.maketrans("ğĞıİöÖüÜşŞçÇ", "gGiIoOuUsScC"))
                    .lower()
                    .replace(" ", "-")
                )
        offers = []
        if "fiyat" not in response.request.url:
            offer = OfferItem()
            offer["link"] = None
            offer["shipping_cost"] = None
            offers.append(offer)
        else:
            data = json.loads(response.css("#__NEXT_DATA__::text").get())
            offers_data = data["props"]["pageProps"]["offers"]
            variants = data["props"]["pageProps"]["product"]["variants"]
            if variants is not None:
                variant_url = tuple([_create_url(v["url"]) for v in variants])
                offer = OfferItem()
                offer["link"] = "variant"
                offer["shipping_cost"] = None
                offer["variant_link"] = variant_url
                offers.append(offer)
            else:
                try:
                    var = data["props"]["pageProps"]["product"]["family"]["variants"]
                except:
                    color = ""
                    for i in response.request.url.split("-"):
                        if i in colors:
                            color = i
                            break
                    for offer_data in itertools.chain(
                        offers_data["offers"], offers_data["sponsoredOffers"]
                    ):
                        if color == "":
                            offers.append(crawl_product("-", "-", offer_data))
                        else:
                            offers.append(crawl_product(color, "-", offer_data))
                    if not offers:
                        offer = OfferItem()
                        if color == "":
                            offer["link"] = ""
                            offer["shipping_cost"] = None
                            offer["variant_color"] = "-"
                            offer["variant_link"] = "-"
                            offers.append(offer)
                        else:
                            offer["link"] = ""
                            offer["shipping_cost"] = None
                            offer["variant_color"] = color
                            offer["variant_link"] = "-"
                            offers.append(offer)
                else:
                    variant = [
                        v["shortTitle"]
                        .translate(str.maketrans("ğĞıİöÖüÜşŞçÇ", "gGiIoOuUsScC"))
                        .lower()
                        for v in var
                    ]
                    variant_url = tuple([_create_url(v["url"]) for v in var])
                    if (
                        any(
                            v.rstrip().replace(" ", "-") in response.request.url
                            for v in variant
                        )
                        or response.request.url in variant_url
                    ):
                        c = [
                            v.rstrip()
                            for v in variant
                            for i in v.split()
                            if i in response.request.url
                        ]
                        variant_color = "".join(max(set(c), key=c.count))
                        print(variant_color)
                        # variant_color = ' '.join([v.rstrip() for v in variant if v.rstrip().replace(' ', '-') in response.request.url])
                        for offer_data in itertools.chain(
                            offers_data["offers"], offers_data["sponsoredOffers"]
                        ):
                            if variant_color.replace(" ", "-") in response.request.url:
                                offers.append(
                                    crawl_product(
                                        variant_color, variant_url, offer_data
                                    )
                                )
                            else:
                                offers.append(crawl_product("-", "-", offer_data))
                        if not offers:
                            offer = OfferItem()
                            offer["link"] = ""
                            offer["shipping_cost"] = None
                            offer["variant_color"] = variant_color
                            offer["variant_link"] = variant_url
                            offers.append(offer)
        return [dict(t) for t in {tuple(d.items()) for d in offers}]


def crawl_product(color, url, data):
    offer = OfferItem()
    offer["title"] = data["title"]
    offer["link"] = data["url"]
    offer["price"] = data["pricePlusTax"]
    # priceShipping: 0 = free shipping; null = + (some unknown) shipping cost
    offer["shipping_cost"] = data["priceShipping"]
    offer["last_updated_at"] = datetime.utcfromtimestamp(data["updateDate"] / 1000)
    offer["variant_color"] = color
    offer["variant_link"] = url
    return offer


def _create_url(url):
    return urljoin("https://www.cimri.com/", url)
