import { Cookie } from "./Types"

export class CustomCookiesJar {
    private _cookies: Cookie[];
    constructor(cookies: Cookie[]) {
        this._cookies = cookies;
    }

    get cookies(): Cookie[] {
        return this._cookies
    }

    set cookies(cookies: Cookie[]) {
        this._cookies = cookies
    }

    clear(): void {
        this._cookies = []
    }

    remove(cookie_name: string): void {
        this._cookies = this._cookies.filter(c => c.name !== cookie_name)
    }

    filter(predicate: (cookie: Cookie) => boolean): Cookie[] {
        this._cookies = this._cookies.filter(predicate)
        return this._cookies
    }

    addMany(cookies: Cookie[]): void {
        cookies.forEach(c => this.add(c))
    }

    add(cookie: Cookie): void {
        let finded_cookie = this.find(cookie.name)
        if (finded_cookie) {
            finded_cookie.value = cookie.value
        } else {
            this._cookies.push(cookie)
        }
    }

    find(cookie_name: string): Cookie | undefined {
        return this._cookies.find(c => c.name === cookie_name)
    }

    rewrite(cookies: Cookie[]): void {
        this._cookies = cookies
    }

    static parse(cookie: string): Cookie[] {
        if (!cookie || cookie === "") return []
        const cookies = cookie.split(",").filter(rc => {
            return rc.includes("=") && rc.split("=").length > 1
        }).map(rc => {
            let raw = rc.split(';').shift()?.split("=");
            let cookie: Cookie = {
                //@ts-ignore
                name: raw.at(0)?.replace(/\s/g, ""),
                //@ts-ignore
                value: raw.at(1)?.replace(/\s/g, "")
            }
            return cookie
        }).filter(el => typeof el.value !== "undefined")
        return cookies
    }

    static parseHeaderString(cookie: string): Cookie[] {
        if (!cookie || cookie === "") return []
        const cookies = cookie.split(";").filter(rc => {
            return rc.includes("=") && rc.split("=").length > 1
        }).map(rc => {
            let raw = rc?.split("=");
            let cookie: Cookie = {
                //@ts-ignore
                name: raw.at(0)?.replace(/\s/g, ""),
                //@ts-ignore
                value: raw.at(1)?.replace(/\s/g, "")
            }
            return cookie
        }).filter(el => typeof el.value !== "undefined")
        return cookies
    };

    static validate(cookies: Cookie[], host: URL): Cookie[] {
        return cookies.map(c => {
            c.path = "/";
            c.domain = host.hostname
            return c
        })
    }

    toString(): string {
        return this._cookies.map(c => `${c.name}=${c.value}`).join("; ")
    }

    static toString(cookies: Cookie[] = []): string {
        return cookies.map(c => `${c.name}=${c.value}`).join("; ")
    }
}
