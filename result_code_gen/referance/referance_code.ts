import { getDefaultConf, defaultEditableConf, defaultOpts, getCacher } from "../Base-Custom/Constants";
import { AsyncHTTPXRequestOptsCustom, defaultConf, editableConf, Item } from "../Base-Custom/Types";
import { InvalidLinkError, NotFoundError } from "../Base-Custom/Errors";
import { JS_Base_Custom } from "../Base-Custom/Base-Custom";
import { getTimestamp } from "../Base-Custom/Utils";
import { Cacher } from "../Base-Custom/Cache";
import { SetType } from "a-parser-types";
import {
    toArray, isBadLink,
    name, price, stock, article, brand, link, timestamp
} from "../Base-Custom/Fields"
import * as cheerio from "cheerio";

//#region Кастомные типы данных
type ResultItem = Item<typeof fields>

//#region Константы
const fields = {
    name, price, stock, article, brand, link, timestamp
}

const HOST = "https://glavsantex.ru"

export class JS_Base_glavsantexru extends JS_Base_Custom {
    static defaultConf: defaultConf = {
        ...getDefaultConf(toArray(fields), "ζ", [isBadLink]),
        parsecodes: { 200: 1, 404: 1 },
        proxyChecker: "fineproxy.org.ru",
        requestdelay: "1,3",
        // Настройки запроса
        engine: "a-parser",
        mode: "normal",
        // Кастомные настройки парсера
    };

    static editableConf: editableConf = [
        ...defaultEditableConf
    ];

    //#region Точка входа
    async parse(set: SetType, results: { [key: string]: any }) {
        if (!set.type || set.type === "none") set.type = "page";
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
        let url = new URL(`${HOST}/search/`)
        url.searchParams.set("query", set.query)
        if (set.page > 1) url.searchParams.set("page", set.page)

        const data = await this.makeRequest(url.href)
        const $ = cheerio.load(data);

        if (set.page === 1) {
            let totalPages = Math.max(...$(".pagination__list > li > a").get().map(item => +$(item).text().trim()).filter(Boolean))
            this.debugger.put(`totalPages = ${totalPages}`)
            for (let page = 2; page <= Math.min(totalPages, +this.conf.pagesCount); page++) {
                this.query.add({ ...set, query: set.query, type: "page", page: page, lvl: 1 });
            }
        }

        let products = $('.item-c__title')
        if (products.length == 0) {
            this.logger.put(`По запросу ${set.query} ничего не найдено`)
            throw new NotFoundError()
        }
        products.slice(0, +this.conf.itemsCount).each((i, product) => {
            let link = `${HOST}${$(product)?.attr("href")}`
            this.query.add({ ...set, query: link, type: "card", lvl: 1 })
        })
    }

    //#region Парсинг товара
    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);

        const name = $('h1').text().trim();
        const price = $('.s-product-price').attr('data-price').formatPrice();
        const stock = $(".pd-descr .stock-info__text").text().includes("В наличии") ? "InStock" : "OutOfStock";
        const article = $(".s-product-sku meta[itemprop='sku']").attr("content").trim();
        const brand = $("[itemprop='brand']").attr("content").trim();
        const link = set.query;
        const timestamp = getTimestamp();

        const item: ResultItem = {
            name, price, stock, article, brand, link, timestamp
        }
        items.push(item);

        cacher.cache = items
        return items;
    }

    //#region Выполнение запроса
    async makeRequest(url: string) {
        const opts: AsyncHTTPXRequestOptsCustom = {
            ...defaultOpts,
            engine: this.conf.engine,
            mode: this.conf.mode,
        };
        this.debugger.put(opts)

        const { success, headers, data } = await this.request("GET", url, {}, opts);
        this.debugger.put(data)

        if (!success || typeof data !== "string") throw new Error("Неудачный запрос");
        if (headers.Status === 404) throw new NotFoundError()

        return data;
    }
}
