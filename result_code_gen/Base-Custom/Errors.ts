export class FlaresolverError extends Error {
    constructor(m: string) {
        super(m);
        this.name = "FlaresolverError"
    }
}

export class UnsolveChallengeError extends Error {
    constructor() {
        super('Данный челендж не может быть решен среди зарегестрированных решалок');
        this.name = "UnsolveChallengeError"
    }
}

export class NotAllowedMethod extends Error {
    constructor(m: 'HEAD' | 'PUT' | 'DELETE' | 'CONNECT' | 'OPTIONS' | 'TRACE' | 'PATCH') {
        super(`Flaresolver не поддерживает ${m}`);
        this.name = "NotAllowedMethod"
    }
}

export class NotAllowedAuthProxy extends Error {
    constructor() {
        super(`CurlCffi не поддерживает прокси с авторизацией`);
        this.name = "NotAllowedAuthProxy"
    }
}

export class BanError extends Error {
    public provider!: string;

    constructor(msg: string) {
        super(msg);
        this.name = "BanError"
    }
}

export class BanCloudflareError extends BanError {
    public provider: string = "CloudFlare"

    constructor() {
        super('Ваш IP адрес был забанен Cloudflare');
        this.name = "BanCloudflareError"
    }
}

export class BanQratorError extends BanError {
    public provider: string = "Qrator"

    constructor() {
        super('Ваш IP адрес был забанен Qrator');
        this.name = "BanQratorError"
    }
}

export class BanServicePipeError extends BanError {
    public provider: string = "ServicePipe"

    constructor() {
        super('Ваш IP адрес был забанен ServicePipe');
        this.name = "BanServicePipeError"
    }
}

export class NotFoundError extends Error {
    constructor(msg: string = 'По данному запросу не найдено ни одного товара') {
        super(msg);
        this.name = 'NotFoundError';
    }
}

export class InvalidLinkError extends Error {
    constructor(msg: string = 'Неверная ссылка') {
        super(msg);
        this.name = 'InvalidLinkError';
    }
}