# -*- coding: utf-8 -*-
import os
import re
import scrapy
from fake_useragent import UserAgent
from crawlms.utils import (
    get_urlparam,
    parse_datetime,
    parse_price,
    parse_shipping_cost,
    safe_cast,
)

from ..items import OfferItem


# pylint: disable=no-self-use
class EpeySpider(scrapy.Spider):
    name = "epey"
    allowed_domains = ["www.epey.com"]
    start_urls = ["https://www.epey.com/akilli-telefonlar/redmi-note-8.html"]

    def parse(self, response):
        offers = self._extract_offers(response)
        next_page_link = response.css("#sayfala .son").get()
        if not next_page_link:
            return offers
        urun_id = response.meta.get(
            "urun_id",
            response.css("script::text").re_first(r"{urun_id:(\d+),sayfa:e}"),
        )
        next_page = response.meta.get("page", 1) + 1
        return [
            response.follow(
                "/kat/urun-fiyat/",
                self.parse_more,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                body=f"urun_id={urun_id}&sayfa={next_page}",
                meta=dict(urun_id=urun_id, page=next_page, offers=offers),
            )
        ]

    def parse_more(self, response):
        offers = response.meta["offers"]
        offers.extend(self._extract_offers(response))
        return offers

    def _extract_offers(self, response):
        product_score = safe_cast(response.css("#puan::attr(data-percent)").get(), int)
        offers = []
        ua = UserAgent()
        count = 0
        for a in response.css(".fiyat > a"):
            if "Hepsiburada" in a.css("a::attr(onclick)").get():
                offers.append(crawl_product(a, ua, product_score))
        for a in response.css(".fiyat > a"):
            if "Hepsiburada" not in a.css("a::attr(onclick)").get():
                count += 1
                offers.append(crawl_product(a, ua, product_score))
                if count == 5:
                    break
        if not offers:
            offer = OfferItem()
            offer["link"] = ""
            offer["shipping_cost"] = None
            offers.append(offer)
        return offers


def crawl_product(a, ua, product_score):
    offer = OfferItem()
    if not a.css(".urun_adi::text").get() is None:
        offer["title"] = a.css(".urun_adi::text").get().strip()
        user_agent = ua.random
        link = f'{a.css("a::attr(href)").get()}/'
        location = os.popen(
            f"curl -x tr-pr.oxylabs.io:30000 -U 'customer-rpandame:LDmA8UcQVC'"
            f" -H 'User-Agent: {user_agent}' -I {link} | grep location"
        ).read()
        offer["link"] = _unwrap_url(re.sub("location: ", "", location))
        if offer["link"] == "":
            offer["link"] = " "
        offer["price"] = parse_price(a.css(".urun_fiyat::text").get())
        offer["shipping_cost"] = parse_shipping_cost(
            a.css(".urun_fiyat span::text").get()
        )
        offer["last_updated_at"] = parse_datetime(
            a.css(".urun_git p::text").get(), settings={"TIMEZONE": "+0300"}
        )
        offer["product_score"] = product_score
        offer["epey_color"] = a.css(".urun_adi > p > span.no ::text").get()
    else:
        offer["link"] = " "
        offer["shipping_cost"] = None
    return offer


def _unwrap_url(url):
    return get_urlparam(url, "url") or url
