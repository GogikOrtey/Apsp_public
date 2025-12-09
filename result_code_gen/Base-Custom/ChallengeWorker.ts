import { BanCloudflareError, BanQratorError, BanServicePipeError } from "./Errors";
import { FlareSolverParams, IChallengeWorker } from "./Types";
import { HeadersType } from "a-parser-types";
import * as cheerio from "cheerio";

export class ChallengeDetector {
    static isCFChallenge(data: string, hdr: HeadersType): 0 | 1 {
        return CloudflareChallengleWorker.isChallenge(data, hdr)
    }

    static isCFBan(data: string, hdr: HeadersType): 0 | 1 {
        return CloudflareChallengleWorker.isBan(data, hdr)
    }

    static isQratorChallenge(data: string, hdr: HeadersType): 0 | 1 {
        return QratorChallengleWorker.isChallenge(data, hdr)
    }

    static isQuratorBan(data: string, hdr: HeadersType): 0 | 1 {
        return QratorChallengleWorker.isBan(data, hdr)
    }

    static isServicePipeChallenge(data: string, hdr: HeadersType): 0 | 1 {
        return ServicePipeChallengleWorker.isChallenge(data, hdr)
    }

    static isServicePipeBan(data: string, hdr: HeadersType): 0 | 1 {
        return ServicePipeChallengleWorker.isBan(data, hdr)
    }
}

export const CloudflareChallengleWorker: IChallengeWorker = {
    providerName: "Cloudflare",
    error: new BanCloudflareError(),
    isChallenge: (data: string, hdr: HeadersType): 0 | 1 => {
        if (hdr.Status !== 403) return 0
        if (hdr["cf-mitigated"] === "challenge") return 1
        const $ = cheerio.load(data, {
            xmlMode: false,
            scriptingEnabled: false,
        });

        const CFChallengeTitles = [
            "Just a moment...",
            "Один момент...",
        ]

        const CFChallengeSelectors = [
            //Cloudflare
            "#cf-challenge-running",
            ".ray_id",
            ".attack-box",
            "#cf-please-wait",
            "#challenge-spinner",
            "#challenge-error-text",
            "#trk_jschal_js",
            //Custom CloudFlare for EbookParadijs, Film-Paleis, MuziekFabriek and Puur-Hollands
            "td.info #js_info",
            //Cloudflare salidzini.lv
            ".cf-turnstile",
            //Fairlane / pararius.com
            "div.vc div.text-box h2",
            "#challenge-form",
        ];

        if (ChallengeDetector.isCFBan(data, hdr)) throw new BanCloudflareError()

        return CFChallengeSelectors.some(selector =>
            $(selector).length > 0
        ) || CFChallengeTitles.some(title => $("title").text().includes(title)) ? 1 : 0;
    },
    isBan: (data: string, hdr: HeadersType): 0 | 1 => {
        if (hdr.Status !== 403) return 0
        const $ = cheerio.load(data);

        const CFAccessDeniedTitles = [
            "Access denied",
            "Attention Required! | Cloudflare",
        ]

        const CFAccessDeniedSelectors = [
            "div.cf-error-title span.cf-code-label span",
            "#cf-error-details div.cf-error-overview h1",
        ]

        if (CFAccessDeniedTitles.some(title => $("title").text().includes(title)) || CFAccessDeniedSelectors.some(selector => $(selector).length > 0)) {
            return 1
        }
        return 0
    },
}

export const QratorChallengleWorker: IChallengeWorker = {
    providerName: "Qrator",
    error: new BanQratorError(),
    isChallenge: (data: string, hdr: HeadersType): 0 | 1 => {
        if (hdr.Status !== 401) return 0
        const $ = cheerio.load(data);
        if ($("[src*='/__qrator/']").length > 0) return 1
        return 0
    },
    isBan: (data: string, hdr: HeadersType): 0 | 1 => {
        if (hdr.Status !== 403) return 0
        const $ = cheerio.load(data);
        if ($("title").text().includes("HTTP 403") && data.includes("403 Error")) return 1
        return 0
    },
}

export const ServicePipeChallengleWorker: IChallengeWorker = {
    providerName: "ServicePipe",
    error: new BanServicePipeError(),
    isChallenge: (data: string, hdr: HeadersType): 0 | 1 => {
        const $ = cheerio.load(data);
        if ($('[src*="servicepipe"], [src*="sp_rotated_captcha"], #id_spinner, .captcha-img').length > 0) return 1
        return 0
    },
    isBan: (data: string, hdr: HeadersType): 0 | 1 => {
        if (data.includes("<h1>Forbidden</h1>") &&
            data.includes("If you are not a bot, please copy the report and send it to our support team.")) return 1
        return 0
    },
}

export const presets: { [key: string]: FlareSolverParams } = {
    cloudflare: {
        preferredChallengeWorker: CloudflareChallengleWorker,
    },
    qrator: {
        preferredChallengeWorker: QratorChallengleWorker,
        trigers: [QratorChallengleWorker.isBan],
    },
    servicepipe: {
        preferredChallengeWorker: ServicePipeChallengleWorker,
        trigers: [ServicePipeChallengleWorker.isBan],
        retries: 5,
    }
}