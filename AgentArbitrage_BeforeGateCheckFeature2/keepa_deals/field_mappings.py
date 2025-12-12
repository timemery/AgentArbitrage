# Restore Dashboard Functionality

# Chunk 1 starts
from .stable_products import (
    get_stat_value,                 # Utility function, not a header
    percent_down_90,                # Percent Down 90
    # Avg. Price 90,
    # Percent Down 365, # Will be imported from stable_calculations
    # Avg. Price 365,
    # Price Now,
    # Price Now Source,
    # Deal found,
    amz_link,                       # AMZ link
    keepa_link,                     # Keepa Link
    get_title,                      # Title
    # last update,
    # last price change,
    # Sales Rank - Reference,
    # Reviews - Rating,
    # Reviews - Review Count,
    # get_fba_pick_pack_fee,          # FBA Pick&Pack Fee # Still need to import this # Corrected: This should be uncommented
    get_fba_pick_pack_fee,          # FBA Pick&Pack Fee
    get_referral_fee_percent,       # Referral Fee %
    tracking_since,                 # Tracking since
    categories_root,                # Categories - Root
    categories_sub,                 # Categories - Sub
    categories_tree,                # Categories - Tree
    get_asin,                       # ASIN
    # Freq. Bought Together,
    # Type,
    manufacturer,                   # Manufacturer
    get_brand,                      # Brand
    # Product Group,
    # Variation Attributes,
    # Item Type,
    author,                         # Author
    # Contributors,
    binding,                        # Binding
    # Number of Items,
    # Number of Pages,
    get_publication_date,           # Publication Date
    # Languages,
    # Package - Quantity
    package_weight,                 # Package Weight
    package_height,                 # Package Height
    package_length,                 # Package Length
    package_width,                  # Package Width
    listed_since,                   # Listed since
    # Edition,
    # Release Date,
    # Format,
    sales_rank_current,             # Sales Rank - Current
    sales_rank_30_days_avg,         # Sales Rank - 30 days avg.
    # Sales Rank - 60 days avg.,
    sales_rank_90_days_avg,         # Sales Rank - 90 days avg.
    sales_rank_180_days_avg,        # Sales Rank - 180 days avg.
    sales_rank_365_days_avg,        # Sales Rank - 365 days avg.
    # Sales Rank - Lowest,
    # Sales Rank - Lowest 365 days,
    # Sales Rank - Highest,
    # Sales Rank - Highest 365 days,
    sales_rank_drops_last_30_days,  # Sales Rank - Drops last 30 days
    # Sales Rank - Drops last 60 days,
    # Sales Rank - Drops last 90 days,
    # Sales Rank - Drops last 180 days,
    sales_rank_drops_last_365_days, # Sales Rank - Drops last 365 days
    # get_buy_box_seller_id,          # Buy Box Seller ID
    buy_box_current,                # Buy Box - Current
    # Buy Box - 30 days avg.,
    # Buy Box - 60 days avg.,
    # Buy Box - 90 days avg.,
    # Buy Box - 180 days avg.,
    buy_box_365_days_avg,           # Buy Box - 365 days avg.
    # Buy Box - Lowest,
    # Buy Box - Lowest 365 days,
    # Buy Box - Highest,
    # Buy Box - Highest 365 days,
    # Buy Box - 90 days OOS,
    # Buy Box - Stock,
    amazon_current,                   # Amazon - Current
    # Amazon - 30 days avg.,
    # Amazon - 60 days avg.,
    # Amazon - 90 days avg.,
    # Amazon - 180 days avg.,
    amazon_365_days_avg,            # Amazon - 365 days avg.
    # Amazon - Lowest,
    # Amazon - Lowest 365 days,
    # Amazon - Highest,
    # Amazon - Highest 365 days,
    # Amazon - 90 days OOS,
    # Amazon - Stock,
    new_current,                    # New - Current,
    # New - 30 days avg.,
    # New - 60 days avg.,
    # New - 90 days avg.,
    # New - 180 days avg.,
    new_365_days_avg,               # New - 365 days avg.,
    # New - Lowest,
    # New - Lowest 365 days,
    # New - Highest,
    # New - Highest 365 days,
    # New - 90 days OOS,
    # New - Stock,
    new_3rd_party_fba_current,      # New, 3rd Party FBA - Current,
    # New, 3rd Party FBA - 30 days avg.,
    # New, 3rd Party FBA - 60 days avg.,
    # New, 3rd Party FBA - 90 days avg.,
    # New, 3rd Party FBA - 180 days avg.,
    new_3rd_party_fba_365_days_avg, # New, 3rd Party FBA - 365 days avg.,
    new_3rd_party_fba_lowest,        # New, 3rd Party FBA - Lowest,
    # New, 3rd Party FBA - Lowest 365 days,
    # New, 3rd Party FBA - Highest,
    # New, 3rd Party FBA - Highest 365 days,
    # New, 3rd Party FBA - 90 days OOS,
    # New, 3rd Party FBA - Stock,
    new_3rd_party_fbm_current,      # New, 3rd Party FBM - Current
    # New, 3rd Party FBM - 30 days avg.,
    # New, 3rd Party FBM - 60 days avg.,
    # New, 3rd Party FBM - 90 days avg.,
    # New, 3rd Party FBM - 180 days avg.,
    new_3rd_party_fbm_365_days_avg, # New, 3rd Party FBM - 365 days avg.
    # New, 3rd Party FBM - Lowest,
    # New, 3rd Party FBM - Lowest 365 days,
    # New, 3rd Party FBM - Highest,
    # New, 3rd Party FBM - Highest 365 days,
    # New, 3rd Party FBM - 90 days OOS,
    # New, 3rd Party FBM - Stock,
    buy_box_used_current,           # Buy Box Used - Current,
    # Buy Box Used - 30 days avg.,
    # Buy Box Used - 60 days avg.,
    # Buy Box Used - 90 days avg.,
    # Buy Box Used - 180 days avg.,
    buy_box_used_365_days_avg,      # Buy Box Used - 365 days avg.,
    # Buy Box Used - Lowest,
    # Buy Box Used - Lowest 365 days,
    # Buy Box Used - Highest,
    # Buy Box Used - Highest 365 days,
    # Buy Box Used - 90 days OOS,
    # Buy Box Used - Stock,
    used_current,                   # Used - Current
    # Used - 30 days avg.,
    # Used - 60 days avg.,
    # Used - 90 days avg.,
    # Used - 180 days avg.,
    used_365_days_avg,              # Used - 365 days avg.
    # Used - Lowest,
    # Used - Lowest 365 days,
    # Used - Highest,
    # Used - Highest 365 days,
    # Used - 90 days OOS,
    # Used - Stock,
    used_like_new,                  # Used, like new - Current
    # Used, like new - 30 days avg.,
    # Used, like new - 60 days avg.,
    # Used, like new - 90 days avg.,
    # Used, like new - 180 days avg.,
    # used_like_new_365_days_avg,     # Used, like new - 365 days avg. # This will be imported from stable_products
    # Used, like new - Lowest,
    # Used, like new - Lowest 365 days,
    # Used, like new - Highest,
    # Used, like new - Highest 365 days,
    # Used, like new - 90 days OOS,
    # Used, like new - Stock,
    used_very_good,                 # Used, very good - Current
    # Used, very good - 30 days avg.,
    # Used, very good - 60 days avg.,
    # Used, very good - 90 days avg.,
    # Used, very good - 180 days avg.,
    used_very_good_365_days_avg,    # Used, very good - 365 days avg.
    # Used, very good - Lowest,
    # Used, very good - Lowest 365 days,
    # Used, very good - Highest,
    # Used, very good - Highest 365 days,
    # Used, very good - 90 days OOS,
    # Used, very good - Stock,
    used_good,                      # Used, good - Current
    # Used, good - 30 days avg.,
    # Used, good - 60 days avg.,
    # Used, good - 90 days avg.,
    # Used, good - 180 days avg.,
    used_good_365_days_avg,         # Used, good - 365 days avg.,
    # Used, good - Lowest,
    # Used, good - Lowest 365 days,
    # Used, good - Highest,
    # Used, good - Highest 365 days,
    # Used, good - 90 days OOS,
    # Used, good - Stock,
    used_acceptable,                # Used, acceptable - Current
    # Used, acceptable - 30 days avg.,
    # Used, acceptable - 60 days avg.,
    # Used, acceptable - 90 days avg.,
    # Used, acceptable - 180 days avg.,
    used_acceptable_365_days_avg,   # Used, acceptable - 365 days avg.,
    # Used, acceptable - Lowest,
    # Used, acceptable - Lowest 365 days,
    # Used, acceptable - Highest,
    # Used, acceptable - Highest 365 days,
    # Used, acceptable - 90 days OOS,
    # Used, acceptable - Stock,
    list_price,                     # List Price - Current
    # List Price - 30 days avg.,
    # List Price - 60 days avg.,
    # List Price - 90 days avg.,
    # List Price - 180 days avg.,
    # List Price - 365 days avg.,
    # List Price - Lowest,
    # List Price - Lowest 365 days,
    # List Price - Highest,
    # List Price - Highest 365 days,
    # List Price - 90 days OOS,
    # List Price - Stock,
    # New Offer Count - Current,
    # New Offer Count - 30 days avg.,
    # New Offer Count - 60 days avg.,
    # New Offer Count - 90 days avg.,
    # New Offer Count - 180 days avg.,
    # New Offer Count - 365 days avg.,
    # Used Offer Count - Current,
    # Used Offer Count - 30 days avg.,
    # Used Offer Count - 60 days avg.,
    # Used Offer Count - 90 days avg.,
    # Used Offer Count - 180 days avg.,
    # Used Offer Count - 365 days avg.
    new_offer_count_current,        # New Offer Count - Current
    new_offer_count_365_days_avg,   # New Offer Count - 365 days avg.
    used_offer_count_current,       # Used Offer Count - Current
    used_offer_count_365_days_avg,  # Used Offer Count - 365 days avg.
    buy_box_365_days_avg,      # Buy Box - 365 days avg.
    new_3rd_party_fbm_365_days_avg, # New, 3rd Party FBM - 365 days avg.
    used_like_new_365_days_avg, # Added import
    get_fba_pick_pack_fee, # Added import for FBA Pick&Pack Fee
    get_referral_fee_percent, # Added import for Referral Fee %
    get_shipping_included,
    profit_margin_percent
)
from .stable_calculations import (
    percent_down_365,               # Percent Down 365
    recent_inferred_sale_price,
    get_peak_season,
    get_list_at_price,
    get_trough_season,
    profit_confidence,
)
# Imports for seller info are no longer needed here, as it's handled in a decoupled loop.
from .stable_deals import (
    # Percent Down 90,
    # Avg. Price 90,
    # Percent Down 365,
    # Avg. Price 365,
    # Price Now,
    # Price Now Source,
    deal_found,                     # Deal found
    get_condition,                  # Condition
    # AMZ link,
    # Keepa Link,
    # Title,
    last_update,                    # last update
    last_price_change,              # last price change
    # Sales Rank - Reference,
    # Reviews - Rating,
    # Reviews - Review Count,
    # FBA Pick&Pack Fee,
    # Referral Fee %,
    # Tracking since,
    # Categories - Root,
    # Categories - Sub,
    # Categories - Tree,
    # ASIN,
    # Freq. Bought Together,
    # Type,
    # Manufacturer,
    # Brand,
    # Product Group,
    # Variation Attributes,
    # Item Type,
    # Author,
    # Contributors,
    # Binding,
    # Number of Items,
    # Number of Pages,
    # Publication Date,
    # Languages,
    # Package - Quantity,
    # Package Weight,
    # Package Height,
    # Package Length,
    # Package Width,
    # Listed since,
    # Edition,
    # Release Date,
    # Format,
    # Sales Rank - Current,
    # Sales Rank - 30 days avg.,
    # Sales Rank - 60 days avg.,
    # Sales Rank - 90 days avg.,
    # Sales Rank - 180 days avg.,
    # Sales Rank - 365 days avg.,
    # Sales Rank - Lowest,
    # Sales Rank - Lowest 365 days,
    # Sales Rank - Highest,
    # Sales Rank - Highest 365 days,
    # Sales Rank - Drops last 30 days,
    # Sales Rank - Drops last 60 days,
    # Sales Rank - Drops last 90 days,
    # Sales Rank - Drops last 180 days,
    # Sales Rank - Drops last 365 days,
    # Buy Box - Current,
    # Buy Box - 30 days avg.,
    # Buy Box - 60 days avg.,
    # Buy Box - 90 days avg.,
    # Buy Box - 180 days avg.,
    # Buy Box - 365 days avg.,
    # Buy Box - Lowest,
    # Buy Box - Lowest 365 days,
    # Buy Box - Highest,
    # Buy Box - Highest 365 days,
    # Buy Box - 90 days OOS,
    # Buy Box - Stock,
    # Amazon - Current,
    # Amazon - 30 days avg.,
    # Amazon - 60 days avg.,
    # Amazon - 90 days avg.,
    # Amazon - 180 days avg.,
    # Amazon - 365 days avg.,
    # Amazon - Lowest,
    # Amazon - Lowest 365 days,
    # Amazon - Highest,
    # Amazon - Highest 365 days,
    # Amazon - 90 days OOS,
    # Amazon - Stock,
    # New - Current,
    # New - 30 days avg.,
    # New - 60 days avg.,
    # New - 90 days avg.,
    # New - 180 days avg.,
    # New - 365 days avg.,
    # New - Lowest,
    # New - Lowest 365 days,
    # New - Highest,
    # New - Highest 365 days,
    # New - 90 days OOS,
    # New - Stock,
    # New, 3rd Party FBA - Current,
    # New, 3rd Party FBA - 30 days avg.,
    # New, 3rd Party FBA - 60 days avg.,
    # New, 3rd Party FBA - 90 days avg.,
    # New, 3rd Party FBA - 180 days avg.,
    # New, 3rd Party FBA - 365 days avg.,
    # New, 3rd Party FBA - Lowest,
    # New, 3rd Party FBA - Lowest 365 days,
    # New, 3rd Party FBA - Highest,
    # New, 3rd Party FBA - Highest 365 days,
    # New, 3rd Party FBA - 90 days OOS,
    # New, 3rd Party FBA - Stock,
    # New, 3rd Party FBM - Current,
    # New, 3rd Party FBM - 30 days avg.,
    # New, 3rd Party FBM - 60 days avg.,
    # New, 3rd Party FBM - 90 days avg.,
    # New, 3rd Party FBM - 180 days avg.,
    # new_3rd_party_fbm_365_days_avg, # New, 3rd Party FBM - 365 days avg. # THIS WAS THE LINGERING ONE
    # New, 3rd Party FBM - Lowest,
    # New, 3rd Party FBM - Lowest 365 days,
    # New, 3rd Party FBM - Highest,
    # New, 3rd Party FBM - Highest 365 days,
    # New, 3rd Party FBM - 90 days OOS,
    # New, 3rd Party FBM - Stock,
    # Buy Box Used - Current,
    # Buy Box Used - 30 days avg.,
    # Buy Box Used - 60 days avg.,
    # Buy Box Used - 90 days avg.,
    # Buy Box Used - 180 days avg.,
    # Buy Box Used - 365 days avg.,
    # Buy Box Used - Lowest,
    # Buy Box Used - Lowest 365 days,
    # Buy Box Used - Highest,
    # Buy Box Used - Highest 365 days,
    # Buy Box Used - 90 days OOS,
    # Buy Box Used - Stock,
    # Used - Current,
    # Used - 30 days avg.,
    # Used - 60 days avg.,
    # Used - 90 days avg.,
    # Used - 180 days avg.,
    # Used - 365 days avg.,
    # Used - Lowest,
    # Used - Lowest 365 days,
    # Used - Highest,
    # Used - Highest 365 days,
    # Used - 90 days OOS,
    # Used - Stock,
    # Used, like new - Current,
    # Used, like new - 30 days avg.,
    # Used, like new - 60 days avg.,
    # Used, like new - 90 days avg.,
    # Used, like new - 180 days avg.,
    # used_like_new_365_days_avg,     # Used, like new - 365 days avg. # Explicitly commented out
    # Used, like new - Lowest,
    # Used, like new - Lowest 365 days,
    # Used, like new - Highest,
    # Used, like new - Highest 365 days,
    # Used, like new - 90 days OOS,
    # Used, like new - Stock,
    # Used, very good - Current,
    # Used, very good - 30 days avg.,
    # Used, very good - 60 days avg.,
    # Used, very good - 90 days avg.,
    # Used, very good - 180 days avg.,
    # Used, very good - 365 days avg.,
    # Used, very good - Lowest,
    # Used, very good - Lowest 365 days,
    # Used, very good - Highest,
    # Used, very good - Highest 365 days,
    # Used, very good - 90 days OOS,
    # Used, very good - Stock,
    # Used, good - Current,
    # Used, good - 30 days avg.,
    # Used, good - 60 days avg.,
    # Used, good - 90 days avg.,
    # Used, good - 180 days avg.,
    # Used, good - 365 days avg.,
    # Used, good - Lowest,
    # Used, good - Lowest 365 days,
    # Used, good - Highest,
    # Used, good - Highest 365 days,
    # Used, good - 90 days OOS,
    # Used, good - Stock,
    # Used, acceptable - Current,
    # Used, acceptable - 30 days avg.,
    # Used, acceptable - 60 days avg.,
    # Used, acceptable - 90 days avg.,
    # Used, acceptable - 180 days avg.,
    # Used, acceptable - 365 days avg.,
    # Used, acceptable - Lowest,
    # Used, acceptable - Lowest 365 days,
    # Used, acceptable - Highest,
    # Used, acceptable - Highest 365 days,
    # Used, acceptable - 90 days OOS,
    # Used, acceptable - Stock,
    # List Price - Current,
    # List Price - 30 days avg.,
    # List Price - 60 days avg.,
    # List Price - 90 days avg.,
    # List Price - 180 days avg.,
    # List Price - 365 days avg.,
    # List Price - Lowest,
    # List Price - Lowest 365 days,
    # List Price - Highest,
    # List Price - Highest 365 days,
    # List Price - 90 days OOS,
    # List Price - Stock,
    # New Offer Count - Current,
    # New Offer Count - 30 days avg.,
    # New Offer Count - 60 days avg.,
    # New Offer Count - 90 days avg.,
    # New Offer Count - 180 days avg.,
    # New Offer Count - 365 days avg.,
    # Used Offer Count - Current,
    # Used Offer Count - 30 days avg.,
    # Used Offer Count - 60 days avg.,
    # Used Offer Count - 90 days avg.,
    # Used Offer Count - 180 days avg.,
    # Used Offer Count - 365 days avg.
)
# Chunk 1 ends

# Chunk 2 starts
FUNCTION_LIST = [
    percent_down_90,                # Percent Down 90
    None,                           # Avg. Price 90
    percent_down_365,               # Percent Down 365
    None,                           # Avg. Price 365
    None,                           # Price Now
    get_shipping_included,          # Shipping Included
    deal_found,                     # Deal found
    amz_link,                       # AMZ link
    keepa_link,                     # Keepa Link
    get_title,                      # Title
    last_update,                    # last update
    last_price_change,              # last price change
    None,                           # Changed
    None,                           # 1yr. Avg.
    None,                           # % ⇩
    None,                           # Trend
    None,                           # Sales Rank - Reference
    None,                           # Reviews - Rating
    None,                           # Reviews - Review Count
    get_fba_pick_pack_fee,          # FBA Pick&Pack Fee
    get_referral_fee_percent,       # Referral Fee %
    tracking_since,                 # Tracking since
    categories_root,                # Categories - Root
    categories_sub,                 # Categories - Sub
    categories_tree,                # Categories - Tree
    get_asin,                       # ASIN
    None,                           # Freq. Bought Together
    None,                           # Type
    manufacturer,                   # Manufacturer
    get_brand,                      # Brand
    None,                           # Product Group
    None,                           # Variation Attributes
    None,                           # Item Type
    author,                         # Author
    None,                           # Contributors
    binding,                        # Binding
    get_condition,                  # Condition
    None,                           # Number of Items
    None,                           # Number of Pages
    get_publication_date,           # Publication Date
    None,                           # Languages
    None,                           # Package - Quantity
    package_weight,                 # Package Weight
    package_height,                 # Package Height
    package_length,                 # Package Length
    package_width,                  # Package Width
    listed_since,                   # Listed since
    None,                           # Edition
    None,                           # Release Date
    None,                           # Format
    sales_rank_current,             # Sales Rank - Current
    sales_rank_30_days_avg,         # Sales Rank - 30 days avg.
    None,                           # Sales Rank - 60 days avg.
    sales_rank_90_days_avg,         # Sales Rank - 90 days avg.
    sales_rank_180_days_avg,        # Sales Rank - 180 days avg.
    sales_rank_365_days_avg,        # Sales Rank - 365 days avg.
    None,                           # Sales Rank - Lowest
    None,                           # Sales Rank - Lowest 365 days
    None,                           # Sales Rank - Highest
    None,                           # Sales Rank - Highest 365 days
    sales_rank_drops_last_30_days,  # Sales Rank - Drops last 30 days
    None,                           # Sales Rank - Drops last 60 days
    None,                           # Sales Rank - Drops last 90 days
    None,                           # Sales Rank - Drops last 180 days
    sales_rank_drops_last_365_days, # Sales Rank - Drops last 365 days
    None,                           # Seller ID (handled in decoupled loop)
    None,                           # Seller
    buy_box_current,                # Buy Box - Current
    None,                           # Buy Box - 30 days avg.
    None,                           # Buy Box - 60 days avg.
    None,                           # Buy Box - 90 days avg.
    None,                           # Buy Box - 180 days avg.
    buy_box_365_days_avg,           # Buy Box - 365 days avg.
    None,                           # Buy Box - Lowest
    None,                           # Buy Box - Lowest 365 days
    None,                           # Buy Box - Highest
    None,                           # Buy Box - Highest 365 days
    None,                           # Buy Box - 90 days OOS
    None,                           # Buy Box - Stock
    amazon_current,                 # Amazon - Current
    None,                           # Amazon - 30 days avg.
    None,                           # Amazon - 60 days avg.
    None,                           # Amazon - 90 days avg.
    None,                           # Amazon - 180 days avg.
    amazon_365_days_avg,            # Amazon - 365 days avg.
    None,                           # Amazon - Lowest
    None,                           # Amazon - Lowest 365 days
    None,                           # Amazon - Highest
    None,                           # Amazon - Highest 365 days
    None,                           # Amazon - 90 days OOS
    None,                           # Amazon - Stock
    new_current,                    # New - Current
    None,                           # New - 30 days avg.
    None,                           # New - 60 days avg.
    None,                           # New - 90 days avg.
    None,                           # New - 180 days avg.
    new_365_days_avg,               # New - 365 days avg.
    None,                           # New - Lowest
    None,                           # New - Lowest 365 days
    None,                           # New - Highest
    None,                           # New - Highest 365 days
    None,                           # New - 90 days OOS
    None,                           # New - Stock
    new_3rd_party_fba_current,      # New, 3rd Party FBA - Current (new_3rd_party_fba_current,)
    None,                           # New, 3rd Party FBA - 30 days avg.
    None,                           # New, 3rd Party FBA - 60 days avg.
    None,                           # New, 3rd Party FBA - 90 days avg.
    None,                           # New, 3rd Party FBA - 180 days avg.
    new_3rd_party_fba_365_days_avg, # New, 3rd Party FBA - 365 days avg.
    new_3rd_party_fba_lowest,       # New, 3rd Party FBA - Lowest
    None,                           # New, 3rd Party FBA - Lowest 365 days
    None,                           # New, 3rd Party FBA - Highest
    None,                           # New, 3rd Party FBA - Highest 365 days
    None,                           # New, 3rd Party FBA - 90 days OOS
    None,                           # New, 3rd Party FBA - Stock
    new_3rd_party_fbm_current,      # New, 3rd Party FBM - Current
    None,                           # New, 3rd Party FBM - 30 days avg.
    None,                           # New, 3rd Party FBM - 60 days avg.
    None,                           # New, 3rd Party FBM - 90 days avg.
    None,                           # New, 3rd Party FBM - 180 days avg.
    new_3rd_party_fbm_365_days_avg, # New, 3rd Party FBM - 365 days avg.
    None,                           # New, 3rd Party FBM - Lowest
    None,                           # New, 3rd Party FBM - Lowest 365 days
    None,                           # New, 3rd Party FBM - Highest
    None,                           # New, 3rd Party FBM - Highest 365 days
    None,                           # New, 3rd Party FBM - 90 days OOS
    None,                           # New, 3rd Party FBM - Stock
    buy_box_used_current,           # Buy Box Used - Current
    None,                           # Buy Box Used - 30 days avg.
    None,                           # Buy Box Used - 60 days avg.
    None,                           # Buy Box Used - 90 days avg.
    None,                           # Buy Box Used - 180 days avg.
    buy_box_used_365_days_avg,      # Buy Box Used - 365 days avg.
    None,                           # Buy Box Used - Lowest
    None,                           # Buy Box Used - Lowest 365 days
    None,                           # Buy Box Used - Highest
    None,                           # Buy Box Used - Highest 365 days
    None,                           # Buy Box Used - 90 days OOS
    None,                           # Buy Box Used - Stock
    used_current,                   # Used - Current
    None,                           # Used - 30 days avg.
    None,                           # Used - 60 days avg.
    None,                           # Used - 90 days avg.
    None,                           # Used - 180 days avg.
    used_365_days_avg,              # Used - 365 days avg.
    None,                           # Used - Lowest
    None,                           # Used - Lowest 365 days
    None,                           # Used - Highest
    None,                           # Used - Highest 365 days
    None,                           # Used - 90 days OOS
    None,                           # Used - Stock
    used_like_new,                  # Used, like new - Current
    None,                           # Used, like new - 30 days avg.
    None,                           # Used, like new - 60 days avg.
    None,                           # Used, like new - 90 days avg.
    None,                           # Used, like new - 180 days avg.
    used_like_new_365_days_avg,     # Used, like new - 365 days avg.
    None,                           # Used, like new - Lowest
    None,                           # Used, like new - Lowest 365 days
    None,                           # Used, like new - Highest
    None,                           # Used, like new - Highest 365 days
    None,                           # Used, like new - 90 days OOS
    None,                           # Used, like new - Stock
    used_very_good,                 # Used, very good - Current
    None,                           # Used, very good - 30 days avg.
    None,                           # Used, very good - 60 days avg.
    None,                           # Used, very good - 90 days avg.
    None,                           # Used, very good - 180 days avg.
    used_very_good_365_days_avg,    # Used, very good - 365 days avg.
    None,                           # Used, very good - Lowest
    None,                           # Used, very good - Lowest 365 days
    None,                           # Used, very good - Highest
    None,                           # Used, very good - Highest 365 days
    None,                           # Used, very good - 90 days OOS
    None,                           # Used, very good - Stock
    used_good,                      # Used, good - Current
    None,                           # Used, good - 30 days avg.
    None,                           # Used, good - 60 days avg.
    None,                           # Used, good - 90 days avg.
    None,                           # Used, good - 180 days avg.
    used_good_365_days_avg,         # Used, good - 365 days avg.
    None,                           # Used, good - Lowest
    None,                           # Used, good - Lowest 365 days
    None,                           # Used, good - Highest
    None,                           # Used, good - Highest 365 days
    None,                           # Used, good - 90 days OOS
    None,                           # Used, good - Stock
    used_acceptable,                # Used, acceptable - Current
    None,                           # Used, acceptable - 30 days avg.
    None,                           # Used, acceptable - 60 days avg.
    None,                           # Used, acceptable - 90 days avg.
    None,                           # Used, acceptable - 180 days avg.
    used_acceptable_365_days_avg,   # Used, acceptable - 365 days avg.
    None,                           # Used, acceptable - Lowest
    None,                           # Used, acceptable - Lowest 365 days
    None,                           # Used, acceptable - Highest
    None,                           # Used, acceptable - Highest 365 days
    None,                           # Used, acceptable - 90 days OOS
    None,                           # Used, acceptable - Stock
    list_price,                         # List Price - Current
    None,                           # List Price - 30 days avg.
    None,                           # List Price - 60 days avg.
    None,                           # List Price - 90 days avg.
    None,                           # List Price - 180 days avg.
    None,                           # List Price - 365 days avg.
    None,                           # List Price - Lowest
    None,                           # List Price - Lowest 365 days
    None,                           # List Price - Highest
    None,                           # List Price - Highest 365 days
    None,                           # List Price - 90 days OOS
    None,                           # List Price - Stock
    new_offer_count_current,        # New Offer Count - Current
    None,                           # New Offer Count - 30 days avg.
    None,                           # New Offer Count - 60 days avg.
    None,                           # New Offer Count - 90 days avg.
    None,                           # New Offer Count - 180 days avg.
    new_offer_count_365_days_avg,   # New Offer Count - 365 days avg.
    used_offer_count_current,       # Used Offer Count - Current
    None,                           # Used Offer Count - 30 days avg.
    None,                           # Used Offer Count - 60 days avg.
    None,                           # Used Offer Count - 90 days avg.
    None,                           # Used Offer Count - 180 days avg.
    used_offer_count_365_days_avg,  # Used Offer Count - 365 days avg.
    None,                           # Seller Rank (handled in decoupled loop)
    None,                           # Seller_Quality_Score (handled in decoupled loop)
    None,                           # Best Price (handled in decoupled loop)
    recent_inferred_sale_price,     # Recent Inferred Sale Price
    None,                           # Seasonality Type
    None,                           # Detailed_Seasonality
    None,                           # Sells
    get_peak_season,                # Peak Season
    get_list_at_price,              # List at
    get_trough_season,              # Trough Season
    None,                           # Expected Trough Price
    profit_confidence,              # Profit Confidence
    None,                           # Min. Listing Price
    None,                           # All-in Cost
    None,                           # Profit
    None,                           # Margin
    None,                           # Total AMZ fees
    None,                           # last_seen_utc
    None                            # source
]
# Chunk 2 ends

#### END of field_mappings.py ####