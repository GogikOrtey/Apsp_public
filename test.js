let products = $('.products .product-card a.stretched-link[href*=\"/products/\"]')
let product = products?.eq(0)
let link = $(product)?.attr('href')
console.log('link = ' + link)