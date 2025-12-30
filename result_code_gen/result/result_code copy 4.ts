import { getDefaultConf, defaultEditableConf, defaultOpts, getCacher } from "../Base-Custom/Constants";
import { AsyncHTTPXRequestOptsCustom, defaultConf, editableConf, Item } from "../Base-Custom/Types";
import { InvalidLinkError, NotFoundError } from "../Base-Custom/Errors";
import { JS_Base_Custom } from "../Base-Custom/Base-Custom";
import { getTimestamp } from "../Base-Custom/Utils";
import { SetType, tools } from "a-parser-types";
import { Cacher } from "../Base-Custom/Cache";
import {
    toArray, isBadLink,
    name, imageLink, article, category, brand, price, oldprice, link, timestamp
} from "../Base-Custom/Fields"
import * as cheerio from "cheerio";

//#region Кастомные типы данных
type ResultItem = Item<typeof fields>

//#region Константы
const fields = {
    name, imageLink, article, category, brand, price, oldprice, link, timestamp
}

const HOST = "https://cosmedel.ru"

export class JS_Base_cosmedelru extends JS_Base_Custom {
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
        async parsePage(set) {
        const url = "https://sort.diginetica.net/search"
        const pageSize = 500;
        const urlParam = {
            st: set.query,
            apiKey: "U449P61K89", // CHANGE_HERE
            strategy: "advanced_xname,zero_queries",
            fullData: true,
            withCorrection: true,
            withFacets: true,
            treeFacets: true,
            regionId: "global",
            useCategoryPrediction: false,
            size: pageSize,
            offset: set.offset,
            showUnavailable: true,
            unavailableMultiplier: 0.2,
            preview: false,
            withSku: false,
            sort: "DEFAULT",
        };

        const data = await this.makeRequest(url, urlParam)
        const json = JSON.parse(data);

        if (json.totalHits == 0) {
            this.logger.put(`По запросу ${set.query} ничего не найдено`)
            throw new NotFoundError()
        }

        if (set.offset === 0) {
            const totalPages = Math.ceil(json.totalHits / pageSize);
            for (let shift = 1; shift <= Math.min(totalPages, +this.conf.pagesCount); shift++) {
                this.query.add(({ ...set, query: set.query, type: "page", offset: shift * pageSize, lvl: 1 }));
            }
        }

        json.products.slice(0, +this.conf.itemsCount).forEach(product => {
            let link = `https://www.cosmedel.ru${product?.link_url}` // CHANGE_HERE
            this.query.add({ ...set, query: link, type: "card", lvl: 1 })
        })
    }


    //#region Парсинг товара
        async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);

        const name = $(".page-product h1")?.first().text().trim();
        const imageLinkPath = $(".page-product .prod-img-slider a.slide.prod-img-zoom[href]")?.first()?.attr("href")?.trim() || "";
        const imageLink = imageLinkPath?.startsWith("http") ? imageLinkPath : (imageLinkPath ? (HOST + imageLinkPath) : "");
        const article = $(".page-product .pit-art")?.first().text()?.replace("Артикул:", "")?.trim() || "";
        const category = $(".mw.crumbs .tbar-menu li:nth-last-child(2) a")?.first().text().trim() || "";
        const brand = $(".page-product .pit-crumbs a")?.first().text().trim() || "";
        const priceText = $(".page-product .prod-buy .prod-price > span")?.first().text().trim() || "";
        const price = priceText?.replace(/,/g, ".")?.replace(/[^\d.]/g, "") || "";
        const oldpriceText = $(".page-product .prod-buy .prod-price > .-old")?.first().text().trim() || "";
        const oldprice = oldpriceText?.replace(/,/g, ".")?.replace(/[^\d.]/g, "") || "";
        const link = set.query;
        const timestamp = getTimestamp()

        const item: ResultItem = {
            name, imageLink, article, category, brand, price, oldprice, link, timestamp
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