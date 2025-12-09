import * as crypto from 'crypto';
import * as fs from 'fs';

import { CacheItems } from './Types';
import { BaseParser } from 'a-parser-types';

export class Cacher<T = any> {
    private readonly parser_name: string;
    private parser?: BaseParser
    private hours?: number;
    private params?: object;
    private force_parse: boolean = false;
    private cache_name?: string

    constructor(parser: string | BaseParser, hours?: number, params?: object, force_parse: boolean = false, cache_name?: string) {
        if (parser instanceof BaseParser) {
            this.parser = parser;
            this.parser_name = parser.constructor.name;
            this.cache_name = cache_name
        } else {
            this.parser_name = parser;
        }
        this.hours = hours;
        this.params = params;
        this.force_parse = force_parse;
    }

    get file() {
        return (
            process.cwd() +
            `/files/cache/` +
            this.parser_name +
            '/' +
            crypto.createHash('sha256').update(JSON.stringify(this.params), 'utf8').digest('hex') +
            '.json'
        );
    }

    get cache(): T | null {
        if (!this.params) throw new Error('Params is undefined');
        if (!this.hours) throw new Error('Hours is undefined');
        if (this.force_parse) return null;
        try {
            const jsonData: CacheItems = JSON.parse(
                fs.readFileSync(this.file, 'utf-8')
            ) as CacheItems;

            // Вычитаем hours часов (hours * 60 * 60 * 1000 миллисекунд)
            const checkTime = new Date(new Date().getTime() - this.hours * 60 * 60 * 1000).getTime();

            if (jsonData.timestamp < checkTime) throw new Error('Нужен повторный запрос');

            if (jsonData.items.length > 0) {
                jsonData.items = jsonData.items.map(function (i: any) {
                    i.timestamp = Math.floor(Date.now() / 1000);
                    return i;
                });
            }

            this.parser?.logger.put(`Нашел ${this.cache_name || "items"} в кеше`)

            return jsonData.items;
        } catch (e) {
            return null;
        }
    }

    getCache(params: object, hours: number = 12): null | T {
        this.params = params;
        this.hours = hours;
        return this.cache;
    }

    set cache(items: T) {
        if (!this.params) throw new Error('Params is undefined');
        if (!this.hours) throw new Error('Hours is undefined');
        const cache: CacheItems = {
            timestamp: Date.now(),
            items: items
        };

        const directoryPath = this.file.split('/').slice(0, -1).join('/');
        if (!fs.existsSync(directoryPath)) {
            fs.mkdirSync(directoryPath, { recursive: true });
        }

        this.parser?.logger.put(`Обновил ${this.cache_name || "items"} кеш`)

        fs.writeFileSync(this.file, JSON.stringify(cache), 'utf-8');
    }

    saveCache(params: object, items: T) {
        this.params = params;
        this.cache = items;
    }
}