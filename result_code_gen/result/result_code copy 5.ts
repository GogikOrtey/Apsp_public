import { getDefaultConf, defaultEditableConf, defaultOpts, getCacher } from "../Base-Custom/Constants";
import { AsyncHTTPXRequestOptsCustom, defaultConf, editableConf, Item } from "../Base-Custom/Types";
import { InvalidLinkError, NotFoundError } from "../Base-Custom/Errors";
import { JS_Base_Custom } from "../Base-Custom/Base-Custom";
import { getTimestamp } from "../Base-Custom/Utils";
import { SetType, tools } from "a-parser-types";
import { Cacher } from "../Base-Custom/Cache";
import {
    toArray, isBadLink,
    name, stock, imageLink, article, category, brand, price, oldprice, link, timestamp
} from "../Base-Custom/Fields"
import * as cheerio from "cheerio";

//#region Кастомные типы данных
type ResultItem = Item<typeof fields>

//#region Константы
const fields = {
    name, stock, imageLink, article, category, brand, price, oldprice, link, timestamp
}

const HOST = "https://domo-terra.ru"

export class JS_Base_domoterraru extends JS_Base_Custom {
    static defaultConf: defaultConf = {
            ...getDefaultConf(toArray(fields), "ζ", [isBadLink]),
            parsecodes: { 200: 1, 404: 1 },
            proxyChecker: "fineproxy.org",
            requestdelay: "3,5",
            engine: "a-parser",
            mode: "normal",
        };

    static editableConf: editableConf = [
        ...defaultEditableConf
    ];

    //#region Точка входа
    async parse(set: SetType, results: { [key: string]: any }) {
        if (!set.type || set.type === "none") set.type = "page";
        if (!set.region || set.region === "none") set.region = "";
        try {
            switch (set.type) {
                case "page": {
                    if (!set.page || set.page === "none") set.page = 1;
                    await this.parsePage(set);
                    results.success = 1;
                    break;
                }
                case "card": {
                    const cacher = getCacher<ResultItem>(this, set)
                    let items = cacher.cache || await this.parseCard(set, cacher);
                    items.forEach(item => results.items.addElement(item));
                    results.success = 1;
                    break;
                }
                default:
                    this.logger.put("Указан неверный тип сбора")
                    results.success = 0;
            }
        } catch (e: any) {
            if (e instanceof NotFoundError || e instanceof InvalidLinkError) {
                this.logger.put(e.message);
                results.isBadLink = 1;
                results.success = 1;
            } else {
                this.logger.put(`${e.name} >> ${e.message}   ${set.query}  type - ${set.type} page ${set.page} }`);
                results.success = 0;
            }
        }
        return results;
    }

    //#region Парсинг поиска
        async parsePage(set: SetType) {
        let url = new URL(`${HOST}/catalog/`)
        url.searchParams.set("q", set.query)
        url.searchParams.set("s", "")
        url.searchParams.set("PAGEN_3", set.page)

        const data = await this.makeRequest(url.href)
        const $ = cheerio.load(data)

        if (set.page === 1) {
            let totalPages = Math.max(...$("#paginator .navigation a, #paginator .navigation span").get().map(item => +$(item).text().trim()).filter(Boolean))
            this.debugger.put(`totalPages = ${totalPages}`)
            for (let page = 2; page <= Math.min(totalPages, +this.conf.pagesCount); page++) {
                this.query.add({ ...set, query: set.query, type: "page", page: page, lvl: 1 });
            }
        }

        let products = $('#view-showcase .list-showcase__name > a[href]')
        if (products.length == 0) {
            this.logger.put(`По запросу ${set.query} ничего не найдено`)
            throw new NotFoundError()
        }
        products.slice(0, +this.conf.itemsCount).each((i, product) => {
            let link = HOST + $(product)?.attr('href')
            this.query.add({ ...set, query: link, type: "card", lvl: 1 })
        })
    }

    //#region Парсинг товара
        async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);

        const name = $("h1.pagetitle").text().trim()
        const stock = $(".js-detail[itemtype='http://schema.org/Product'] [itemprop='offers'] link[itemprop='availability']")?.first()?.attr("href")?.includes("http://schema.org/OutOfStock") ? "OutOfStock" : "InStock"
        const imageLinkRaw = $(".js-detail[itemtype='http://schema.org/Product'] link[itemprop='image']")?.first()?.attr("href") || ""
        const imageLinkOg = $("meta[property='og:image']")?.first()?.attr("content") || ""
        const imageLinkImg = $(".detail__pic img[src], .detail__pic img[data-src], .detail__pic img[srcset]")?.first()?.attr("src") || $(".detail__pic img[src], .detail__pic img[data-src], .detail__pic img[srcset]")?.first()?.attr("data-src") || $(".detail__pic img[src], .detail__pic img[data-src], .detail__pic img[srcset]")?.first()?.attr("srcset") || ""
        const imageLinkAny = (imageLinkRaw || imageLinkOg || imageLinkImg || "").trim()
        const imageLink = imageLinkAny
          ? (imageLinkAny.startsWith("http") ? imageLinkAny : HOST + imageLinkAny)
          : ""
        const article = $(".c-gruppedprops__prop-value")?.first().text().trim()
        const category = $(".js-detail[itemtype='http://schema.org/Product'] meta[itemprop='category']")?.first()?.attr("content")?.trim() || ""
        const brand = $(".c-gruppedprops__prop:contains('Бренд') .c-gruppedprops__prop-value, .c-gruppedprops__prop:contains('Производитель') .c-gruppedprops__prop-value, .c-gruppedprops__prop:contains('Марка') .c-gruppedprops__prop-value")?.first().text().trim()
        const price = $(".js-detail[itemtype='http://schema.org/Product'] [itemprop='offers'] meta[itemprop='price']")?.first()?.attr("content")?.trim() || ""
        const oldpriceText = $(".c-prices__value-old")?.first().text().trim() || ""
        const oldprice = oldpriceText?.replace(/[^\d]/g, "") || ""
        const link = set.query;
        const timestamp = getTimestamp()

        const item: ResultItem = {
            name, stock, imageLink, article, category, brand, price, oldprice, link, timestamp
        }
        items.push(item);

        // Отладочный вывод всех полей
        if (this.conf.debug) items.forEach(elem => { Object.entries(elem).forEach(([key, value]) => { this.debugger.put(`🟩 ${key} = ${value}`) }) });

        cacher.cache = items
        return items;
    }
    

    //#region Выполнение запроса
    async makeRequest(url: string, urlPrams = {}) {
        const opts: AsyncHTTPXRequestOptsCustom = {
            ...defaultOpts,
            engine: this.conf.engine,
            mode: this.conf.mode,
        };
        this.debugger.put(opts)

        const { success, headers, data } = await this.request("GET", url, urlPrams, opts);
        this.debugger.put(data)

        if (!success || typeof data !== "string") throw new Error("Неудачный запрос");
        if (headers.Status === 404) throw new NotFoundError();

        return data;
    }
}

// Код сгенерирован Auto-gen parsers v1.0
// Дата: 30 Дек 2025
// © BrandPol