Hello Keepa Support Team,

We are working on a project to build a persistent, local database that stays in sync with Keepa's data, and we would be very grateful for your guidance on the recommended best practices.

Our goal is to create a system that:

1. Initially populates our database with a full set of deals based on our filter criteria.
2. After the initial population, it should only fetch deals that have been newly added or recently changed, to keep our local database up-to-date without making unnecessary API calls and consuming tokens.

We have been exploring the `/deal` endpoint, which seems perfect for this purpose. However, we want to ensure we are using it in the most efficient and correct way.

Could you please point us to any documentation, examples, or best practice guides that describe the recommended workflow for this kind of incremental synchronization? Specifically, we're interested in:

- The best parameters to use with the `/deal` endpoint to reliably find only the "delta" (i.e., new or changed deals) since our last check.
- The recommended architectural pattern for combining the `/deal` endpoint (for finding changes) and the `/product` endpoint (for getting the full, updated product data).

Any advice or links to relevant documentation you could provide would be immensely helpful and would ensure we are using your fantastic API as efficiently and respectfully as possible.

Thank you for your time and support.

Best regards, Tim Emery



Hi Tim,

Here’s a sketch of how to keep a local DB somewhat in sync with Keepa. 

\1) Initial backfill
Call /deal with your filters, sort by “newest/most-recent change”, and paginate until exhausted. Store a watermark = the newest “last update/change” timestamp you observed.
For the returned ASINs, call the Product request.

\2) Incremental sync (delta)
On each poll, call /deal with the same filters and keep the sort newest first. Stop paginating as soon as a deal’s timestamp ≤ your watermark; everything above it is your delta.
Fetch full details for just those ASINs via /product.

\3) Practical tips
Keep one watermark per filter set you run.



Docs you can skim for parameters/examples:

- [Browsing Deals](https://keepa.com/#!discuss/t/browsing-deals/338)
- [Products](https://keepa.com/#!discuss/t/products/110)
- [Deal Object](https://keepa.com/#!discuss/t/deal-object/412)
- [Product Object](https://keepa.com/#!discuss/t/product-object/116)

Regards,

Marius