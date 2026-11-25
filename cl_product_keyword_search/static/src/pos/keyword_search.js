/** @odoo-module */
// Copyright (C) Code Legion (https://thecodelegion.com). License LGPL-3.0 or later.

import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { unaccent } from "@web/core/utils/strings";

// The standard search box looks in each product's `searchString`. The keywords
// of the product are added to that text; the search itself is left as it is.
patch(ProductProduct.prototype, {
    get searchString() {
        return [super.searchString, this.cl_variant_search_text].filter(Boolean).join(" ");
    },
});

// The standard search wants the typed text in one piece. When it finds nothing
// and several words were typed, show the products that carry every word (in
// their name, reference, barcode or keywords). Results of the standard search
// are never changed.
patch(ProductScreen.prototype, {
    getProductsBySearchWord(searchWord) {
        const found = super.getProductsBySearchWord(...arguments);
        const words = unaccent(searchWord.toLowerCase(), false).split(/\s+/).filter(Boolean);
        if (found.length || words.length < 2) {
            return found;
        }
        const candidates = this.pos.selectedCategory?.id
            ? this.getProductsByCategory(this.pos.selectedCategory)
            : this.products;
        return candidates.filter((product) => {
            const text = unaccent(product.searchString);
            return words.every((word) => text.includes(word));
        });
    },
});
