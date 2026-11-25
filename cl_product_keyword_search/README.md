# Product Keyword Search (`cl_product_keyword_search`)

Find products by your own keywords, in the backend, the web shop and the Point of Sale. By [Code Legion](https://thecodelegion.com).

People rarely search for a product by the name on its form: they type a nickname, an old reference or what a competitor calls it. Put those words on the product and it is found by them wherever a product is searched.

## What it does

- **Search keywords on the product**: On the General Information tab, shared by all variants. A single variant can have extra keywords of its own.
- **Backend**: Product drop-downs (orders, invoices, transfers...), searching other documents by product, and a "Search Keyword" field in the product lists.
- **Web shop**: The shop search and its search-as-you-type suggestions, including the "did you mean" correction.
- **Point of Sale**: The product search box.
- **Several words**: Every typed word has to be found.
- **Keyword list**: Sales > Configuration > Products > Search Keywords, to rename or colour keywords and see where they are used. The product lists have a "Without Search Keywords" filter.

## Behaves well

- Exact lookups are left alone: a barcode scan, an import matching products by name or any other "equals" search never returns extra products.
- No extra query per search: the keywords of a product are kept in one indexed text column and a search is one more condition on it.
- In drop-downs, Odoo's own matches come first; products found by keyword fill the rest of the list.
- The Point of Sale search is extended, not replaced. Odoo's results are never changed; only when it finds nothing for several words are products carrying every word shown.
- A keyword cannot exist twice (case and extra spaces are ignored); typing an existing one on a product picks it.
- Quick to install on large catalogues: nothing is computed per product at install time.

## Technical

- Model `cl.product.search.keyword` (`name`, `match_key`, `color`, `template_ids`, `variant_ids`).
- `cl_search_keyword_ids` and stored `cl_keyword_search_text` on `product.template`; `cl_variant_keyword_ids` and stored `cl_variant_search_text` on `product.product` (trigram-indexed when `pg_trgm` is available).
- Backend through `_search_display_name()` on both models and `product.product.name_search()`; web shop through `_search_get_detail()` and `_add_search_subdomains_hook()`; POS through `_load_pos_data_fields()` and a patch of `searchString` / `getProductsBySearchWord` that calls the original.
- Tests: `odoo -i cl_product_keyword_search --test-tags /cl_product_keyword_search`.
- Odoo 18.0 · depends on `product`, `point_of_sale`, `website_sale` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
