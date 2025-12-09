import iconv from 'iconv-lite';
import * as cheerio from "cheerio";
import { JS_Base_Custom } from './Base-Custom';


export function getTimestamp(): number {
    return Math.floor(Date.now() / 1000);
}

export function encodeToWindows1251(string: string): string {
    const encodedBuffer = iconv.encode(string, 'win1251');
    let encodedResult = "";
    for (let i = 0; i < encodedBuffer.length; i++) {
        const byte = encodedBuffer[i];
        encodedResult += "%" + byte.toString(16).toUpperCase();
    }
    return encodedResult;
}

export function randUuid() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (J) => {
        const R = (Math.random() * 16) | 0;
        return (J === "x" ? R : (R & 3) | 8).toString(16);
    });
};

export function hexGenerator(length: number) {
    let result = '';
    const characters = 'abcdef0123456789';
    const charactersLength = characters.length;
    for (let i = 0; i < length; i++) {
        result += characters.charAt(Math.floor(Math.random() * charactersLength));
    }
    return result;
}

export function textWithoutChildren(elem) {
    const $ = cheerio.load(''); // Создаем пустой объект cheerio
    const cloned = $(elem).clone(); // Клонируем переданный элемент
    cloned.children().remove(); // Удаляем дочерние элементы из клонированного элемента
    return cloned.text().trim(); // Получаем текст из клонированного элемента без дочерних элементов
}

export function clone(obj: any) {
    return JSON.parse(JSON.stringify(obj))
}

export function randInt(min: number, max: number) {
    return Math.round(Math.random() * (max - min) + min);
}

export async function updateDelayByProxyUsage(parser: JS_Base_Custom) {
    const data = await fetch("http://10.0.0.69/rest/proxy/traffic").then(res => res.text()).then(JSON.parse)
    const traffic = +data?.traffic

    if (!Number.isNaN(traffic)) {
        if (traffic > 2000) parser.requestDelay = "13,15"
        else if (traffic > 1500) parser.requestDelay = "10,13"
        else if (traffic > 1000) parser.requestDelay = "7,10"
        else parser.requestDelay = "5,7"
    } else parser.requestDelay = "60"
}

export function deserializeDataGraph(data: any[]) {
    function processIndex(index: number): any {
        const result: any = {};
        if (index >= data.length) return index;

        const item = data[index];

        if (item === null || item === undefined) return item;

        if (Array.isArray(item)) {
            if (
                item.length === 2 &&
                typeof item[0] === "string" &&
                /^(Ref|ShallowRef|ShallowReactive|Reactive|ComputedRef|EmptyRef)$/i.test(item[0])
            )
                return processIndex(item[1]);
            return item.map((i) => processIndex(i));
        }

        if (typeof item === "object") {
            for (const [key, value] of Object.entries(item || {})) {
                if (typeof value === "number") result[key] = processIndex(value);
            }
            return result;
        }

        return item;
    }
    return processIndex(0);
}