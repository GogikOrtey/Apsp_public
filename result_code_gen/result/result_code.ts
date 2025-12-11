import { getDefaultConf, defaultEditableConf, defaultOpts, getCacher } from "../Base-Custom/Constants";
import { AsyncHTTPXRequestOptsCustom, defaultConf, editableConf, Item } from "../Base-Custom/Types";
import { InvalidLinkError, NotFoundError } from "../Base-Custom/Errors";
import { JS_Base_Custom } from "../Base-Custom/Base-Custom";
import { getTimestamp } from "../Base-Custom/Utils";
import { SetType, tools } from "a-parser-types";
import { Cacher } from "../Base-Custom/Cache";
import {
    toArray, isBadLink,
    name, stock, link, price, article, imageLink, timestamp
} from "../Base-Custom/Fields"
import * as cheerio from "cheerio";

//#region Кастомные типы данных
type ResultItem = Item<typeof fields>

//#region Константы
const fields = {
    name, stock, link, price, article, imageLink, timestamp
}

const HOST = "https://gresstore.ru"

export class JS_Base_gresstoreru extends JS_Base_Custom {
    static defaultConf: defaultConf = {
            ...getDefaultConf(toArray(fields), "ζ", [isBadLink]),
            parsecodes: { 200: 1, 404: 1 },
            proxyChecker: "tor.proxy.ru",
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
        let url = new URL(`${HOST}/search/?search=${set.query}`)
		url.searchParams.set("page", set.page)

        const data = await this.makeRequest(url.href)
        const $ = cheerio.load(data)

        if (set.page === 1) {
            let totalPages = Math.max(...$("div.col-sm-6.text-right").get().map(item => +$(item).text().trim()).filter(Boolean)) 
            this.debugger.put(`totalPages = ${totalPages}`)
            for (let page = 2; page <= Math.min(totalPages, +this.conf.pagesCount); page++) {
                this.query.add({ ...set, query: set.query, type: "page", page: page, lvl: 1 });
            }
        }
        
        let products = $("div.image > a[href]") 
        if (products.length == 0) {
            this.logger.put(`По запросу ${set.query} ничего не найдено`)
            throw new NotFoundError()
        }
        products.slice(0, +this.conf.itemsCount).each((i, product) => {
            let link = $(product)?.attr("href")
            this.query.add({ ...set, query: link, type: "card", lvl: 1 })
        }) 
    }

    //#region Парсинг товара
    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $ = cheerio.load(data);

        const name = $("h1").text()?.trim()
		const stock = $(".html.dopinfo_tpl.dopinfo > .dopinfo_item > a").text()?.includes("Самовывоз.") ? "InStock" : "OutOfStock"
		const link = set.query
		const price = $(".item_price").text()?.trim().formatPrice(",")
const article = $("span.text_atr > a").text()?.trim()?.toLowerCase()?.replace(/\s/g, '-');
const imageLink = $("meta")?.attr("property")?.trim()?.at(0)?.split('/').at(0) + "//" + HOST + $("meta")?.attr("property")?.trim()?.at(0)?.split('/').at(2) + "-" + $("meta")?.attr("property")?.trim()?.at(0)?.split('/').at(3) + ".webp" || ""
        const timestamp = getTimestamp()

        const item: ResultItem = {
            name, stock, link, price, article, imageLink, timestamp
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
        if (headers.Status === 404) throw new NotFoundError();

        return data;
    }
}

// Код сгенерирован APSP v0.1
// Дата: 11 Дек 2025
// © BrandPol