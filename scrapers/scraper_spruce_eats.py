#!/usr/bin/env python3
"""The Spruce Eats scraper for cooking basics, recipes, and meal planning.

Covers:
  - Cooking basics (techniques, methods, kitchen safety)
  - Recipes (appetizers, mains, desserts, soups, salads)
  - World cuisines (American, Asian, European, Latin, etc.)
  - Ingredients, baking, beverages, and meal planning
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class SpruceEatsScraper(BaseScraper):
    """Scrape The Spruce Eats cooking guides, recipes, and meal planning articles."""

    SOURCES = {
        "cooking-basics": {
            "pages": {
                # Fundamental techniques
                "https://www.thespruceeats.com/how-to-saute-food-995692": "How to Saute Food",
                "https://www.thespruceeats.com/what-is-braising-995569": "What Is Braising",
                "https://www.thespruceeats.com/knife-skills-for-beginners-995498": "Knife Skills for Beginners",
                "https://www.thespruceeats.com/how-to-roast-vegetables-995701": "How to Roast Vegetables",
                "https://www.thespruceeats.com/how-to-blanch-vegetables-995478": "How to Blanch Vegetables",
                "https://www.thespruceeats.com/how-to-deglaze-a-pan-995489": "How to Deglaze a Pan",
                "https://www.thespruceeats.com/how-to-poach-food-995695": "How to Poach Food",
                "https://www.thespruceeats.com/grilling-basics-for-beginners-995502": "Grilling Basics for Beginners",
                "https://www.thespruceeats.com/how-to-deep-fry-food-995487": "How to Deep Fry Food",
                "https://www.thespruceeats.com/what-is-searing-995571": "What Is Searing",
                "https://www.thespruceeats.com/how-to-steam-food-995710": "How to Steam Food",
                "https://www.thespruceeats.com/what-is-stewing-995573": "What Is Stewing",
                "https://www.thespruceeats.com/how-to-broil-food-995481": "How to Broil Food",
                "https://www.thespruceeats.com/how-to-baste-food-995475": "How to Baste Food",
                "https://www.thespruceeats.com/what-is-reducing-a-sauce-995567": "What Is Reducing a Sauce",
                "https://www.thespruceeats.com/how-to-flambe-safely-995494": "How to Flambe Safely",
                "https://www.thespruceeats.com/how-to-julienne-vegetables-995507": "How to Julienne Vegetables",
                "https://www.thespruceeats.com/how-to-chiffonade-herbs-995484": "How to Chiffonade Herbs",
                "https://www.thespruceeats.com/how-to-brunoise-cut-995480": "How to Brunoise Cut",
                "https://www.thespruceeats.com/what-is-mise-en-place-995563": "What Is Mise en Place",
                # Kitchen safety and food handling
                "https://www.thespruceeats.com/kitchen-safety-tips-995511": "Kitchen Safety Tips",
                "https://www.thespruceeats.com/food-safety-temperatures-995496": "Food Safety Temperatures",
                "https://www.thespruceeats.com/how-to-prevent-cross-contamination-995697": "How to Prevent Cross Contamination",
                "https://www.thespruceeats.com/proper-handwashing-in-the-kitchen-995699": "Proper Handwashing in the Kitchen",
                "https://www.thespruceeats.com/how-to-store-food-safely-995713": "How to Store Food Safely",
                "https://www.thespruceeats.com/how-long-do-leftovers-last-995515": "How Long Do Leftovers Last",
                "https://www.thespruceeats.com/danger-zone-food-temperature-995488": "Danger Zone Food Temperature",
                "https://www.thespruceeats.com/how-to-thaw-food-safely-995716": "How to Thaw Food Safely",
                "https://www.thespruceeats.com/safe-minimum-cooking-temperatures-995708": "Safe Minimum Cooking Temperatures",
                "https://www.thespruceeats.com/how-to-calibrate-a-thermometer-995482": "How to Calibrate a Thermometer",
                # Essential cooking skills
                "https://www.thespruceeats.com/how-to-season-cast-iron-995709": "How to Season Cast Iron",
                "https://www.thespruceeats.com/how-to-sharpen-kitchen-knives-995711": "How to Sharpen Kitchen Knives",
                "https://www.thespruceeats.com/how-to-make-a-roux-995703": "How to Make a Roux",
                "https://www.thespruceeats.com/how-to-make-stock-995704": "How to Make Stock",
                "https://www.thespruceeats.com/how-to-temper-chocolate-995714": "How to Temper Chocolate",
                "https://www.thespruceeats.com/how-to-caramelize-onions-995483": "How to Caramelize Onions",
                "https://www.thespruceeats.com/how-to-make-a-pan-sauce-995700": "How to Make a Pan Sauce",
                "https://www.thespruceeats.com/how-to-emulsify-a-sauce-995491": "How to Emulsify a Sauce",
                "https://www.thespruceeats.com/how-to-truss-a-chicken-995717": "How to Truss a Chicken",
                "https://www.thespruceeats.com/how-to-debone-a-chicken-995490": "How to Debone a Chicken",
                "https://www.thespruceeats.com/how-to-fillet-a-fish-995493": "How to Fillet a Fish",
                "https://www.thespruceeats.com/how-to-peel-tomatoes-995696": "How to Peel Tomatoes",
                "https://www.thespruceeats.com/how-to-dice-an-onion-995492": "How to Dice an Onion",
                "https://www.thespruceeats.com/how-to-mince-garlic-995518": "How to Mince Garlic",
                "https://www.thespruceeats.com/how-to-zest-citrus-995719": "How to Zest Citrus",
                # Kitchen equipment and tools
                "https://www.thespruceeats.com/essential-kitchen-tools-995523": "Essential Kitchen Tools",
                "https://www.thespruceeats.com/types-of-kitchen-knives-995521": "Types of Kitchen Knives",
                "https://www.thespruceeats.com/choosing-cookware-guide-995486": "Choosing Cookware Guide",
                "https://www.thespruceeats.com/cast-iron-vs-stainless-steel-995522": "Cast Iron vs Stainless Steel",
                "https://www.thespruceeats.com/how-to-use-a-food-processor-995495": "How to Use a Food Processor",
                "https://www.thespruceeats.com/how-to-use-a-stand-mixer-995712": "How to Use a Stand Mixer",
                "https://www.thespruceeats.com/how-to-use-an-immersion-blender-995506": "How to Use an Immersion Blender",
                "https://www.thespruceeats.com/essential-baking-tools-995524": "Essential Baking Tools",
                "https://www.thespruceeats.com/best-cutting-boards-guide-995526": "Best Cutting Boards Guide",
                "https://www.thespruceeats.com/kitchen-thermometer-guide-995510": "Kitchen Thermometer Guide",
                # Cooking methods and tips
                "https://www.thespruceeats.com/how-to-cook-with-wine-995485": "How to Cook with Wine",
                "https://www.thespruceeats.com/cooking-with-fresh-herbs-995527": "Cooking with Fresh Herbs",
                "https://www.thespruceeats.com/how-to-make-marinades-995517": "How to Make Marinades",
                "https://www.thespruceeats.com/how-to-make-a-brine-995516": "How to Make a Brine",
                "https://www.thespruceeats.com/understanding-heat-transfer-995529": "Understanding Heat Transfer",
                "https://www.thespruceeats.com/smoking-food-for-beginners-995530": "Smoking Food for Beginners",
                "https://www.thespruceeats.com/how-to-cure-meat-at-home-995531": "How to Cure Meat at Home",
                "https://www.thespruceeats.com/fermentation-basics-995532": "Fermentation Basics",
                "https://www.thespruceeats.com/sous-vide-cooking-guide-995533": "Sous Vide Cooking Guide",
                "https://www.thespruceeats.com/pressure-cooking-basics-995534": "Pressure Cooking Basics",
                "https://www.thespruceeats.com/slow-cooker-tips-and-tricks-995535": "Slow Cooker Tips and Tricks",
                "https://www.thespruceeats.com/wok-cooking-basics-995536": "Wok Cooking Basics",
                "https://www.thespruceeats.com/how-to-use-a-dutch-oven-995537": "How to Use a Dutch Oven",
                "https://www.thespruceeats.com/outdoor-cooking-essentials-995538": "Outdoor Cooking Essentials",
                "https://www.thespruceeats.com/how-to-season-food-properly-995539": "How to Season Food Properly",
            },
        },
        "recipes": {
            "pages": {
                # Chicken recipes
                "https://www.thespruceeats.com/best-chicken-recipes-4163436": "Best Chicken Recipes",
                "https://www.thespruceeats.com/easy-pasta-recipes-4163437": "Easy Pasta Recipes",
                "https://www.thespruceeats.com/best-soup-recipes-4163438": "Best Soup Recipes",
                "https://www.thespruceeats.com/classic-roast-chicken-recipe-995601": "Classic Roast Chicken",
                "https://www.thespruceeats.com/chicken-parmesan-recipe-995602": "Chicken Parmesan",
                "https://www.thespruceeats.com/lemon-herb-chicken-thighs-995603": "Lemon Herb Chicken Thighs",
                "https://www.thespruceeats.com/honey-garlic-chicken-recipe-995604": "Honey Garlic Chicken",
                "https://www.thespruceeats.com/chicken-stir-fry-recipe-995605": "Chicken Stir Fry",
                "https://www.thespruceeats.com/creamy-tuscan-chicken-995606": "Creamy Tuscan Chicken",
                "https://www.thespruceeats.com/chicken-tikka-masala-recipe-995607": "Chicken Tikka Masala",
                "https://www.thespruceeats.com/buffalo-chicken-wings-recipe-995608": "Buffalo Chicken Wings",
                # Beef and pork
                "https://www.thespruceeats.com/classic-beef-stew-recipe-995609": "Classic Beef Stew",
                "https://www.thespruceeats.com/perfect-steak-recipe-995610": "Perfect Steak Recipe",
                "https://www.thespruceeats.com/beef-tacos-recipe-995611": "Beef Tacos",
                "https://www.thespruceeats.com/meatloaf-recipe-995612": "Classic Meatloaf",
                "https://www.thespruceeats.com/beef-bourguignon-recipe-995613": "Beef Bourguignon",
                "https://www.thespruceeats.com/pulled-pork-recipe-995614": "Pulled Pork",
                "https://www.thespruceeats.com/pork-chops-recipe-995615": "Pork Chops Recipe",
                "https://www.thespruceeats.com/baby-back-ribs-recipe-995616": "Baby Back Ribs",
                "https://www.thespruceeats.com/braised-short-ribs-recipe-995617": "Braised Short Ribs",
                "https://www.thespruceeats.com/beef-stroganoff-recipe-995618": "Beef Stroganoff",
                # Seafood
                "https://www.thespruceeats.com/pan-seared-salmon-recipe-995619": "Pan Seared Salmon",
                "https://www.thespruceeats.com/shrimp-scampi-recipe-995620": "Shrimp Scampi",
                "https://www.thespruceeats.com/fish-tacos-recipe-995621": "Fish Tacos",
                "https://www.thespruceeats.com/baked-cod-recipe-995622": "Baked Cod",
                "https://www.thespruceeats.com/lobster-bisque-recipe-995623": "Lobster Bisque",
                "https://www.thespruceeats.com/grilled-tuna-steak-recipe-995624": "Grilled Tuna Steak",
                "https://www.thespruceeats.com/crab-cakes-recipe-995625": "Crab Cakes",
                # Pasta and rice
                "https://www.thespruceeats.com/spaghetti-carbonara-recipe-995626": "Spaghetti Carbonara",
                "https://www.thespruceeats.com/fettuccine-alfredo-recipe-995627": "Fettuccine Alfredo",
                "https://www.thespruceeats.com/lasagna-recipe-995628": "Classic Lasagna",
                "https://www.thespruceeats.com/mac-and-cheese-recipe-995629": "Mac and Cheese",
                "https://www.thespruceeats.com/penne-alla-vodka-recipe-995630": "Penne alla Vodka",
                "https://www.thespruceeats.com/mushroom-risotto-recipe-995631": "Mushroom Risotto",
                "https://www.thespruceeats.com/fried-rice-recipe-995632": "Fried Rice",
                "https://www.thespruceeats.com/spanish-rice-recipe-995633": "Spanish Rice",
                # Soups and stews
                "https://www.thespruceeats.com/chicken-noodle-soup-recipe-995634": "Chicken Noodle Soup",
                "https://www.thespruceeats.com/tomato-soup-recipe-995635": "Tomato Soup",
                "https://www.thespruceeats.com/french-onion-soup-recipe-995636": "French Onion Soup",
                "https://www.thespruceeats.com/minestrone-soup-recipe-995637": "Minestrone Soup",
                "https://www.thespruceeats.com/clam-chowder-recipe-995638": "Clam Chowder",
                "https://www.thespruceeats.com/potato-leek-soup-recipe-995639": "Potato Leek Soup",
                "https://www.thespruceeats.com/chili-recipe-995640": "Classic Chili",
                "https://www.thespruceeats.com/butternut-squash-soup-recipe-995641": "Butternut Squash Soup",
                "https://www.thespruceeats.com/split-pea-soup-recipe-995642": "Split Pea Soup",
                "https://www.thespruceeats.com/lentil-soup-recipe-995643": "Lentil Soup",
                # Salads
                "https://www.thespruceeats.com/caesar-salad-recipe-995644": "Caesar Salad",
                "https://www.thespruceeats.com/greek-salad-recipe-995645": "Greek Salad",
                "https://www.thespruceeats.com/cobb-salad-recipe-995646": "Cobb Salad",
                "https://www.thespruceeats.com/waldorf-salad-recipe-995647": "Waldorf Salad",
                "https://www.thespruceeats.com/caprese-salad-recipe-995648": "Caprese Salad",
                "https://www.thespruceeats.com/tabbouleh-salad-recipe-995649": "Tabbouleh Salad",
                "https://www.thespruceeats.com/asian-chicken-salad-recipe-995650": "Asian Chicken Salad",
                # Appetizers
                "https://www.thespruceeats.com/bruschetta-recipe-995651": "Bruschetta",
                "https://www.thespruceeats.com/spinach-artichoke-dip-recipe-995652": "Spinach Artichoke Dip",
                "https://www.thespruceeats.com/deviled-eggs-recipe-995653": "Deviled Eggs",
                "https://www.thespruceeats.com/stuffed-mushrooms-recipe-995654": "Stuffed Mushrooms",
                "https://www.thespruceeats.com/hummus-recipe-995655": "Classic Hummus",
                "https://www.thespruceeats.com/guacamole-recipe-995656": "Guacamole",
                "https://www.thespruceeats.com/shrimp-cocktail-recipe-995657": "Shrimp Cocktail",
                "https://www.thespruceeats.com/caprese-skewers-recipe-995658": "Caprese Skewers",
                # Breakfast
                "https://www.thespruceeats.com/fluffy-pancakes-recipe-995659": "Fluffy Pancakes",
                "https://www.thespruceeats.com/french-toast-recipe-995660": "French Toast",
                "https://www.thespruceeats.com/eggs-benedict-recipe-995661": "Eggs Benedict",
                "https://www.thespruceeats.com/classic-omelet-recipe-995662": "Classic Omelet",
                "https://www.thespruceeats.com/breakfast-burrito-recipe-995663": "Breakfast Burrito",
                "https://www.thespruceeats.com/overnight-oats-recipe-995664": "Overnight Oats",
                "https://www.thespruceeats.com/homemade-granola-recipe-995665": "Homemade Granola",
                "https://www.thespruceeats.com/waffles-recipe-995666": "Classic Waffles",
                "https://www.thespruceeats.com/shakshuka-recipe-995667": "Shakshuka",
                # Desserts
                "https://www.thespruceeats.com/chocolate-mousse-recipe-995668": "Chocolate Mousse",
                "https://www.thespruceeats.com/creme-brulee-recipe-995669": "Creme Brulee",
                "https://www.thespruceeats.com/tiramisu-recipe-995670": "Tiramisu",
                "https://www.thespruceeats.com/panna-cotta-recipe-995671": "Panna Cotta",
                "https://www.thespruceeats.com/apple-crisp-recipe-995672": "Apple Crisp",
                "https://www.thespruceeats.com/cheesecake-recipe-995673": "Classic Cheesecake",
                "https://www.thespruceeats.com/banana-pudding-recipe-995674": "Banana Pudding",
                "https://www.thespruceeats.com/bread-pudding-recipe-995675": "Bread Pudding",
                "https://www.thespruceeats.com/ice-cream-recipe-995676": "Homemade Ice Cream",
                "https://www.thespruceeats.com/fruit-tart-recipe-995677": "Fruit Tart",
                # Vegetarian and vegan
                "https://www.thespruceeats.com/vegetable-stir-fry-recipe-995678": "Vegetable Stir Fry",
                "https://www.thespruceeats.com/black-bean-burgers-recipe-995679": "Black Bean Burgers",
                "https://www.thespruceeats.com/eggplant-parmesan-recipe-995680": "Eggplant Parmesan",
                "https://www.thespruceeats.com/stuffed-peppers-recipe-995681": "Stuffed Peppers",
                "https://www.thespruceeats.com/vegetable-curry-recipe-995682": "Vegetable Curry",
                "https://www.thespruceeats.com/tofu-stir-fry-recipe-995683": "Tofu Stir Fry",
                "https://www.thespruceeats.com/cauliflower-steaks-recipe-995684": "Cauliflower Steaks",
                "https://www.thespruceeats.com/chickpea-curry-recipe-995685": "Chickpea Curry",
                # Sandwiches and wraps
                "https://www.thespruceeats.com/club-sandwich-recipe-995686": "Club Sandwich",
                "https://www.thespruceeats.com/grilled-cheese-recipe-995687": "Grilled Cheese",
                "https://www.thespruceeats.com/blt-sandwich-recipe-995688": "BLT Sandwich",
                "https://www.thespruceeats.com/chicken-wrap-recipe-995689": "Chicken Wrap",
                "https://www.thespruceeats.com/philly-cheesesteak-recipe-995690": "Philly Cheesesteak",
                "https://www.thespruceeats.com/reuben-sandwich-recipe-995691": "Reuben Sandwich",
                # Side dishes
                "https://www.thespruceeats.com/mashed-potatoes-recipe-995540": "Mashed Potatoes",
                "https://www.thespruceeats.com/roasted-brussels-sprouts-recipe-995541": "Roasted Brussels Sprouts",
                "https://www.thespruceeats.com/coleslaw-recipe-995542": "Classic Coleslaw",
                "https://www.thespruceeats.com/cornbread-recipe-995543": "Cornbread",
                "https://www.thespruceeats.com/garlic-bread-recipe-995544": "Garlic Bread",
                "https://www.thespruceeats.com/scalloped-potatoes-recipe-995545": "Scalloped Potatoes",
            },
        },
        "cuisines": {
            "pages": {
                # Asian cuisines
                "https://www.thespruceeats.com/chinese-recipes-4163421": "Chinese Recipes",
                "https://www.thespruceeats.com/italian-recipes-4163422": "Italian Recipes",
                "https://www.thespruceeats.com/mexican-recipes-4163423": "Mexican Recipes",
                "https://www.thespruceeats.com/japanese-recipes-4163424": "Japanese Recipes",
                "https://www.thespruceeats.com/thai-recipes-4163441": "Thai Recipes",
                "https://www.thespruceeats.com/korean-recipes-4163442": "Korean Recipes",
                "https://www.thespruceeats.com/vietnamese-recipes-4163443": "Vietnamese Recipes",
                "https://www.thespruceeats.com/indian-recipes-4163444": "Indian Recipes",
                "https://www.thespruceeats.com/filipino-recipes-4163445": "Filipino Recipes",
                "https://www.thespruceeats.com/indonesian-recipes-4163446": "Indonesian Recipes",
                "https://www.thespruceeats.com/malaysian-recipes-4163447": "Malaysian Recipes",
                # European cuisines
                "https://www.thespruceeats.com/french-recipes-4163448": "French Recipes",
                "https://www.thespruceeats.com/spanish-recipes-4163449": "Spanish Recipes",
                "https://www.thespruceeats.com/greek-recipes-4163450": "Greek Recipes",
                "https://www.thespruceeats.com/german-recipes-4163451": "German Recipes",
                "https://www.thespruceeats.com/british-recipes-4163452": "British Recipes",
                "https://www.thespruceeats.com/portuguese-recipes-4163453": "Portuguese Recipes",
                "https://www.thespruceeats.com/polish-recipes-4163454": "Polish Recipes",
                "https://www.thespruceeats.com/scandinavian-recipes-4163455": "Scandinavian Recipes",
                "https://www.thespruceeats.com/russian-recipes-4163456": "Russian Recipes",
                "https://www.thespruceeats.com/hungarian-recipes-4163457": "Hungarian Recipes",
                "https://www.thespruceeats.com/swiss-recipes-4163458": "Swiss Recipes",
                # Latin American cuisines
                "https://www.thespruceeats.com/brazilian-recipes-4163459": "Brazilian Recipes",
                "https://www.thespruceeats.com/cuban-recipes-4163460": "Cuban Recipes",
                "https://www.thespruceeats.com/peruvian-recipes-4163461": "Peruvian Recipes",
                "https://www.thespruceeats.com/argentinian-recipes-4163462": "Argentinian Recipes",
                "https://www.thespruceeats.com/colombian-recipes-4163463": "Colombian Recipes",
                "https://www.thespruceeats.com/caribbean-recipes-4163464": "Caribbean Recipes",
                "https://www.thespruceeats.com/puerto-rican-recipes-4163465": "Puerto Rican Recipes",
                "https://www.thespruceeats.com/venezuelan-recipes-4163466": "Venezuelan Recipes",
                # Middle Eastern cuisines
                "https://www.thespruceeats.com/middle-eastern-recipes-4163467": "Middle Eastern Recipes",
                "https://www.thespruceeats.com/turkish-recipes-4163468": "Turkish Recipes",
                "https://www.thespruceeats.com/lebanese-recipes-4163469": "Lebanese Recipes",
                "https://www.thespruceeats.com/persian-recipes-4163470": "Persian Recipes",
                "https://www.thespruceeats.com/moroccan-recipes-4163471": "Moroccan Recipes",
                "https://www.thespruceeats.com/egyptian-recipes-4163472": "Egyptian Recipes",
                "https://www.thespruceeats.com/israeli-recipes-4163473": "Israeli Recipes",
                # African cuisines
                "https://www.thespruceeats.com/african-recipes-4163474": "African Recipes",
                "https://www.thespruceeats.com/ethiopian-recipes-4163475": "Ethiopian Recipes",
                "https://www.thespruceeats.com/nigerian-recipes-4163476": "Nigerian Recipes",
                "https://www.thespruceeats.com/south-african-recipes-4163477": "South African Recipes",
                "https://www.thespruceeats.com/west-african-recipes-4163478": "West African Recipes",
                "https://www.thespruceeats.com/east-african-recipes-4163479": "East African Recipes",
                # American cuisines
                "https://www.thespruceeats.com/american-recipes-4163480": "American Recipes",
                "https://www.thespruceeats.com/southern-recipes-4163481": "Southern Recipes",
                "https://www.thespruceeats.com/cajun-creole-recipes-4163482": "Cajun and Creole Recipes",
                "https://www.thespruceeats.com/tex-mex-recipes-4163483": "Tex-Mex Recipes",
                "https://www.thespruceeats.com/new-england-recipes-4163484": "New England Recipes",
                "https://www.thespruceeats.com/soul-food-recipes-4163485": "Soul Food Recipes",
                "https://www.thespruceeats.com/hawaiian-recipes-4163486": "Hawaiian Recipes",
                "https://www.thespruceeats.com/pacific-northwest-recipes-4163487": "Pacific Northwest Recipes",
                # Cuisine techniques and guides
                "https://www.thespruceeats.com/guide-to-dim-sum-995546": "Guide to Dim Sum",
                "https://www.thespruceeats.com/guide-to-sushi-making-995547": "Guide to Sushi Making",
                "https://www.thespruceeats.com/guide-to-tapas-995548": "Guide to Tapas",
                "https://www.thespruceeats.com/guide-to-meze-platters-995549": "Guide to Meze Platters",
                "https://www.thespruceeats.com/guide-to-curry-types-995550": "Guide to Curry Types",
                "https://www.thespruceeats.com/guide-to-dumpling-types-995551": "Guide to Dumpling Types",
                "https://www.thespruceeats.com/guide-to-noodle-dishes-995552": "Guide to Noodle Dishes",
                "https://www.thespruceeats.com/guide-to-bbq-styles-995553": "Guide to BBQ Styles",
                "https://www.thespruceeats.com/guide-to-chili-peppers-995554": "Guide to Chili Peppers",
                "https://www.thespruceeats.com/guide-to-fermented-foods-995555": "Guide to Fermented Foods",
                "https://www.thespruceeats.com/guide-to-street-food-995556": "Guide to Street Food",
                "https://www.thespruceeats.com/guide-to-rice-varieties-995557": "Guide to Rice Varieties",
                "https://www.thespruceeats.com/guide-to-flatbreads-995558": "Guide to Flatbreads",
                "https://www.thespruceeats.com/guide-to-pickled-foods-995559": "Guide to Pickled Foods",
                "https://www.thespruceeats.com/guide-to-spice-blends-995560": "Guide to Spice Blends",
            },
        },
        "ingredients": {
            "pages": {
                # Meat guides
                "https://www.thespruceeats.com/all-about-beef-cuts-995304": "All About Beef Cuts",
                "https://www.thespruceeats.com/types-of-cheese-guide-591474": "Types of Cheese Guide",
                "https://www.thespruceeats.com/herb-guide-for-cooking-995327": "Herb Guide for Cooking",
                "https://www.thespruceeats.com/guide-to-pork-cuts-995305": "Guide to Pork Cuts",
                "https://www.thespruceeats.com/guide-to-lamb-cuts-995306": "Guide to Lamb Cuts",
                "https://www.thespruceeats.com/guide-to-poultry-types-995307": "Guide to Poultry Types",
                "https://www.thespruceeats.com/guide-to-ground-meat-995308": "Guide to Ground Meat",
                "https://www.thespruceeats.com/guide-to-cured-meats-995309": "Guide to Cured Meats",
                "https://www.thespruceeats.com/guide-to-sausage-types-995310": "Guide to Sausage Types",
                # Seafood guides
                "https://www.thespruceeats.com/guide-to-fish-types-995311": "Guide to Fish Types",
                "https://www.thespruceeats.com/guide-to-shellfish-types-995312": "Guide to Shellfish Types",
                "https://www.thespruceeats.com/guide-to-shrimp-varieties-995313": "Guide to Shrimp Varieties",
                "https://www.thespruceeats.com/guide-to-salmon-types-995314": "Guide to Salmon Types",
                "https://www.thespruceeats.com/sustainable-seafood-guide-995315": "Sustainable Seafood Guide",
                "https://www.thespruceeats.com/how-to-buy-fresh-fish-995316": "How to Buy Fresh Fish",
                # Vegetable guides
                "https://www.thespruceeats.com/guide-to-leafy-greens-995317": "Guide to Leafy Greens",
                "https://www.thespruceeats.com/guide-to-root-vegetables-995318": "Guide to Root Vegetables",
                "https://www.thespruceeats.com/guide-to-squash-varieties-995319": "Guide to Squash Varieties",
                "https://www.thespruceeats.com/guide-to-mushroom-types-995320": "Guide to Mushroom Types",
                "https://www.thespruceeats.com/guide-to-pepper-varieties-995321": "Guide to Pepper Varieties",
                "https://www.thespruceeats.com/guide-to-onion-types-995322": "Guide to Onion Types",
                "https://www.thespruceeats.com/guide-to-tomato-varieties-995323": "Guide to Tomato Varieties",
                "https://www.thespruceeats.com/guide-to-potato-types-995324": "Guide to Potato Types",
                "https://www.thespruceeats.com/seasonal-vegetable-guide-995325": "Seasonal Vegetable Guide",
                "https://www.thespruceeats.com/how-to-store-vegetables-995326": "How to Store Vegetables",
                # Fruit guides
                "https://www.thespruceeats.com/guide-to-citrus-fruits-995328": "Guide to Citrus Fruits",
                "https://www.thespruceeats.com/guide-to-berry-types-995329": "Guide to Berry Types",
                "https://www.thespruceeats.com/guide-to-tropical-fruits-995330": "Guide to Tropical Fruits",
                "https://www.thespruceeats.com/guide-to-stone-fruits-995331": "Guide to Stone Fruits",
                "https://www.thespruceeats.com/guide-to-apple-varieties-995332": "Guide to Apple Varieties",
                "https://www.thespruceeats.com/seasonal-fruit-guide-995333": "Seasonal Fruit Guide",
                # Grains and legumes
                "https://www.thespruceeats.com/guide-to-rice-types-995334": "Guide to Rice Types",
                "https://www.thespruceeats.com/guide-to-pasta-shapes-995335": "Guide to Pasta Shapes",
                "https://www.thespruceeats.com/guide-to-whole-grains-995336": "Guide to Whole Grains",
                "https://www.thespruceeats.com/guide-to-flour-types-995337": "Guide to Flour Types",
                "https://www.thespruceeats.com/guide-to-beans-and-legumes-995338": "Guide to Beans and Legumes",
                "https://www.thespruceeats.com/guide-to-lentil-types-995339": "Guide to Lentil Types",
                "https://www.thespruceeats.com/guide-to-ancient-grains-995340": "Guide to Ancient Grains",
                # Dairy and eggs
                "https://www.thespruceeats.com/guide-to-milk-types-995341": "Guide to Milk Types",
                "https://www.thespruceeats.com/guide-to-butter-types-995342": "Guide to Butter Types",
                "https://www.thespruceeats.com/guide-to-yogurt-types-995343": "Guide to Yogurt Types",
                "https://www.thespruceeats.com/guide-to-cream-types-995344": "Guide to Cream Types",
                "https://www.thespruceeats.com/guide-to-egg-sizes-and-grades-995345": "Guide to Egg Sizes and Grades",
                # Herbs, spices, and oils
                "https://www.thespruceeats.com/guide-to-dried-herbs-995346": "Guide to Dried Herbs",
                "https://www.thespruceeats.com/guide-to-common-spices-995347": "Guide to Common Spices",
                "https://www.thespruceeats.com/guide-to-cooking-oils-995348": "Guide to Cooking Oils",
                "https://www.thespruceeats.com/guide-to-vinegar-types-995349": "Guide to Vinegar Types",
                "https://www.thespruceeats.com/guide-to-salt-types-995350": "Guide to Salt Types",
                "https://www.thespruceeats.com/guide-to-sweeteners-995351": "Guide to Sweeteners",
                "https://www.thespruceeats.com/guide-to-hot-sauces-995352": "Guide to Hot Sauces",
                "https://www.thespruceeats.com/guide-to-soy-sauce-types-995353": "Guide to Soy Sauce Types",
                "https://www.thespruceeats.com/guide-to-mustard-types-995354": "Guide to Mustard Types",
                # Pantry staples
                "https://www.thespruceeats.com/essential-pantry-staples-995355": "Essential Pantry Staples",
                "https://www.thespruceeats.com/guide-to-canned-goods-995356": "Guide to Canned Goods",
                "https://www.thespruceeats.com/guide-to-dried-fruits-995357": "Guide to Dried Fruits",
                "https://www.thespruceeats.com/guide-to-nuts-and-seeds-995358": "Guide to Nuts and Seeds",
                "https://www.thespruceeats.com/guide-to-chocolate-types-995359": "Guide to Chocolate Types",
            },
        },
        "baking": {
            "pages": {
                # Bread
                "https://www.thespruceeats.com/basic-bread-recipe-427045": "Basic Bread Recipe",
                "https://www.thespruceeats.com/easy-chocolate-cake-recipe-995138": "Easy Chocolate Cake Recipe",
                "https://www.thespruceeats.com/best-cookie-recipes-4163439": "Best Cookie Recipes",
                "https://www.thespruceeats.com/sourdough-bread-recipe-427046": "Sourdough Bread Recipe",
                "https://www.thespruceeats.com/french-baguette-recipe-427047": "French Baguette Recipe",
                "https://www.thespruceeats.com/ciabatta-bread-recipe-427048": "Ciabatta Bread Recipe",
                "https://www.thespruceeats.com/challah-bread-recipe-427049": "Challah Bread Recipe",
                "https://www.thespruceeats.com/focaccia-bread-recipe-427050": "Focaccia Bread Recipe",
                "https://www.thespruceeats.com/brioche-bread-recipe-427051": "Brioche Bread Recipe",
                "https://www.thespruceeats.com/whole-wheat-bread-recipe-427052": "Whole Wheat Bread Recipe",
                "https://www.thespruceeats.com/dinner-rolls-recipe-427053": "Dinner Rolls Recipe",
                "https://www.thespruceeats.com/banana-bread-recipe-427054": "Banana Bread Recipe",
                "https://www.thespruceeats.com/pumpkin-bread-recipe-427055": "Pumpkin Bread Recipe",
                "https://www.thespruceeats.com/zucchini-bread-recipe-427056": "Zucchini Bread Recipe",
                # Cakes
                "https://www.thespruceeats.com/vanilla-cake-recipe-427057": "Vanilla Cake Recipe",
                "https://www.thespruceeats.com/red-velvet-cake-recipe-427058": "Red Velvet Cake Recipe",
                "https://www.thespruceeats.com/carrot-cake-recipe-427059": "Carrot Cake Recipe",
                "https://www.thespruceeats.com/pound-cake-recipe-427060": "Pound Cake Recipe",
                "https://www.thespruceeats.com/angel-food-cake-recipe-427061": "Angel Food Cake Recipe",
                "https://www.thespruceeats.com/german-chocolate-cake-recipe-427062": "German Chocolate Cake Recipe",
                "https://www.thespruceeats.com/lemon-cake-recipe-427063": "Lemon Cake Recipe",
                "https://www.thespruceeats.com/coconut-cake-recipe-427064": "Coconut Cake Recipe",
                "https://www.thespruceeats.com/buttercream-frosting-recipe-427065": "Buttercream Frosting Recipe",
                "https://www.thespruceeats.com/cream-cheese-frosting-recipe-427066": "Cream Cheese Frosting Recipe",
                # Cookies
                "https://www.thespruceeats.com/chocolate-chip-cookies-recipe-427067": "Chocolate Chip Cookies",
                "https://www.thespruceeats.com/oatmeal-cookies-recipe-427068": "Oatmeal Cookies",
                "https://www.thespruceeats.com/sugar-cookies-recipe-427069": "Sugar Cookies",
                "https://www.thespruceeats.com/peanut-butter-cookies-recipe-427070": "Peanut Butter Cookies",
                "https://www.thespruceeats.com/snickerdoodles-recipe-427071": "Snickerdoodles",
                "https://www.thespruceeats.com/shortbread-cookies-recipe-427072": "Shortbread Cookies",
                "https://www.thespruceeats.com/macarons-recipe-427073": "French Macarons",
                "https://www.thespruceeats.com/biscotti-recipe-427074": "Biscotti Recipe",
                "https://www.thespruceeats.com/gingerbread-cookies-recipe-427075": "Gingerbread Cookies",
                # Pies and tarts
                "https://www.thespruceeats.com/apple-pie-recipe-427076": "Apple Pie Recipe",
                "https://www.thespruceeats.com/pumpkin-pie-recipe-427077": "Pumpkin Pie Recipe",
                "https://www.thespruceeats.com/pecan-pie-recipe-427078": "Pecan Pie Recipe",
                "https://www.thespruceeats.com/cherry-pie-recipe-427079": "Cherry Pie Recipe",
                "https://www.thespruceeats.com/blueberry-pie-recipe-427080": "Blueberry Pie Recipe",
                "https://www.thespruceeats.com/lemon-meringue-pie-recipe-427081": "Lemon Meringue Pie Recipe",
                "https://www.thespruceeats.com/pie-crust-recipe-427082": "Pie Crust Recipe",
                "https://www.thespruceeats.com/tart-crust-recipe-427083": "Tart Crust Recipe",
                # Pastry
                "https://www.thespruceeats.com/croissant-recipe-427084": "Croissant Recipe",
                "https://www.thespruceeats.com/danish-pastry-recipe-427085": "Danish Pastry Recipe",
                "https://www.thespruceeats.com/puff-pastry-recipe-427086": "Puff Pastry Recipe",
                "https://www.thespruceeats.com/cinnamon-rolls-recipe-427087": "Cinnamon Rolls Recipe",
                "https://www.thespruceeats.com/scones-recipe-427088": "Scones Recipe",
                "https://www.thespruceeats.com/muffins-recipe-427089": "Classic Muffins Recipe",
                "https://www.thespruceeats.com/eclairs-recipe-427090": "Eclairs Recipe",
                "https://www.thespruceeats.com/cream-puffs-recipe-427091": "Cream Puffs Recipe",
                # Baking basics
                "https://www.thespruceeats.com/baking-powder-vs-baking-soda-427092": "Baking Powder vs Baking Soda",
                "https://www.thespruceeats.com/how-to-proof-yeast-427093": "How to Proof Yeast",
                "https://www.thespruceeats.com/baking-substitutions-guide-427094": "Baking Substitutions Guide",
                "https://www.thespruceeats.com/measuring-ingredients-accurately-427095": "Measuring Ingredients Accurately",
                "https://www.thespruceeats.com/how-to-cream-butter-and-sugar-427096": "How to Cream Butter and Sugar",
                "https://www.thespruceeats.com/how-to-fold-batter-427097": "How to Fold Batter",
                "https://www.thespruceeats.com/how-to-make-meringue-427098": "How to Make Meringue",
                "https://www.thespruceeats.com/how-to-make-whipped-cream-427099": "How to Make Whipped Cream",
            },
        },
        "beverages": {
            "pages": {
                # Cocktails
                "https://www.thespruceeats.com/classic-cocktails-4163419": "Classic Cocktails",
                "https://www.thespruceeats.com/coffee-brewing-guide-765830": "Coffee Brewing Guide",
                "https://www.thespruceeats.com/types-of-tea-guide-765831": "Types of Tea Guide",
                "https://www.thespruceeats.com/margarita-recipe-765832": "Classic Margarita",
                "https://www.thespruceeats.com/old-fashioned-recipe-765833": "Old Fashioned",
                "https://www.thespruceeats.com/mojito-recipe-765834": "Classic Mojito",
                "https://www.thespruceeats.com/manhattan-recipe-765835": "Manhattan Cocktail",
                "https://www.thespruceeats.com/martini-recipe-765836": "Classic Martini",
                "https://www.thespruceeats.com/cosmopolitan-recipe-765837": "Cosmopolitan",
                "https://www.thespruceeats.com/negroni-recipe-765838": "Negroni",
                "https://www.thespruceeats.com/daiquiri-recipe-765839": "Classic Daiquiri",
                "https://www.thespruceeats.com/whiskey-sour-recipe-765840": "Whiskey Sour",
                "https://www.thespruceeats.com/mai-tai-recipe-765841": "Mai Tai",
                "https://www.thespruceeats.com/pina-colada-recipe-765842": "Pina Colada",
                "https://www.thespruceeats.com/bloody-mary-recipe-765843": "Bloody Mary",
                "https://www.thespruceeats.com/moscow-mule-recipe-765844": "Moscow Mule",
                "https://www.thespruceeats.com/gin-and-tonic-recipe-765845": "Gin and Tonic",
                "https://www.thespruceeats.com/tom-collins-recipe-765846": "Tom Collins",
                "https://www.thespruceeats.com/paloma-recipe-765847": "Paloma",
                "https://www.thespruceeats.com/aperol-spritz-recipe-765848": "Aperol Spritz",
                # Coffee and espresso
                "https://www.thespruceeats.com/how-to-make-espresso-765849": "How to Make Espresso",
                "https://www.thespruceeats.com/french-press-coffee-guide-765850": "French Press Coffee Guide",
                "https://www.thespruceeats.com/pour-over-coffee-guide-765851": "Pour Over Coffee Guide",
                "https://www.thespruceeats.com/cold-brew-coffee-recipe-765852": "Cold Brew Coffee",
                "https://www.thespruceeats.com/latte-recipe-765853": "How to Make a Latte",
                "https://www.thespruceeats.com/cappuccino-recipe-765854": "Cappuccino Recipe",
                "https://www.thespruceeats.com/iced-coffee-recipe-765855": "Iced Coffee Recipe",
                "https://www.thespruceeats.com/turkish-coffee-recipe-765856": "Turkish Coffee Recipe",
                # Tea
                "https://www.thespruceeats.com/how-to-brew-green-tea-765857": "How to Brew Green Tea",
                "https://www.thespruceeats.com/how-to-make-chai-tea-765858": "How to Make Chai Tea",
                "https://www.thespruceeats.com/matcha-latte-recipe-765859": "Matcha Latte Recipe",
                "https://www.thespruceeats.com/iced-tea-recipe-765860": "Iced Tea Recipe",
                "https://www.thespruceeats.com/herbal-tea-guide-765861": "Herbal Tea Guide",
                "https://www.thespruceeats.com/bubble-tea-recipe-765862": "Bubble Tea Recipe",
                # Smoothies and juices
                "https://www.thespruceeats.com/green-smoothie-recipe-765863": "Green Smoothie",
                "https://www.thespruceeats.com/berry-smoothie-recipe-765864": "Berry Smoothie",
                "https://www.thespruceeats.com/tropical-smoothie-recipe-765865": "Tropical Smoothie",
                "https://www.thespruceeats.com/protein-smoothie-recipe-765866": "Protein Smoothie",
                "https://www.thespruceeats.com/fresh-juice-recipes-765867": "Fresh Juice Recipes",
                "https://www.thespruceeats.com/lemonade-recipe-765868": "Classic Lemonade",
                # Wine and beer
                "https://www.thespruceeats.com/wine-pairing-guide-765869": "Wine Pairing Guide",
                "https://www.thespruceeats.com/types-of-red-wine-765870": "Types of Red Wine",
                "https://www.thespruceeats.com/types-of-white-wine-765871": "Types of White Wine",
                "https://www.thespruceeats.com/beer-styles-guide-765872": "Beer Styles Guide",
                "https://www.thespruceeats.com/craft-beer-guide-765873": "Craft Beer Guide",
                "https://www.thespruceeats.com/homebrewing-basics-765874": "Homebrewing Basics",
                # Non-alcoholic
                "https://www.thespruceeats.com/mocktail-recipes-765875": "Mocktail Recipes",
                "https://www.thespruceeats.com/hot-chocolate-recipe-765876": "Hot Chocolate Recipe",
                "https://www.thespruceeats.com/eggnog-recipe-765877": "Eggnog Recipe",
                "https://www.thespruceeats.com/apple-cider-recipe-765878": "Apple Cider Recipe",
            },
        },
        "meal-planning": {
            "pages": {
                # Budget meals
                "https://www.thespruceeats.com/budget-friendly-meals-4163425": "Budget Friendly Meals",
                "https://www.thespruceeats.com/meal-prep-ideas-4163426": "Meal Prep Ideas",
                "https://www.thespruceeats.com/holiday-cooking-guide-4163427": "Holiday Cooking Guide",
                "https://www.thespruceeats.com/cheap-dinner-ideas-4163428": "Cheap Dinner Ideas",
                "https://www.thespruceeats.com/grocery-shopping-on-a-budget-4163429": "Grocery Shopping on a Budget",
                "https://www.thespruceeats.com/pantry-meals-ideas-4163430": "Pantry Meals Ideas",
                "https://www.thespruceeats.com/five-ingredient-meals-4163431": "Five Ingredient Meals",
                "https://www.thespruceeats.com/batch-cooking-guide-4163432": "Batch Cooking Guide",
                "https://www.thespruceeats.com/freezer-meal-recipes-4163433": "Freezer Meal Recipes",
                "https://www.thespruceeats.com/leftover-makeover-ideas-4163434": "Leftover Makeover Ideas",
                # Meal prep and planning
                "https://www.thespruceeats.com/weekly-meal-planning-guide-4163435": "Weekly Meal Planning Guide",
                "https://www.thespruceeats.com/sunday-meal-prep-routine-4163488": "Sunday Meal Prep Routine",
                "https://www.thespruceeats.com/make-ahead-breakfasts-4163489": "Make Ahead Breakfasts",
                "https://www.thespruceeats.com/meal-prep-containers-guide-4163490": "Meal Prep Containers Guide",
                "https://www.thespruceeats.com/portion-control-guide-4163491": "Portion Control Guide",
                "https://www.thespruceeats.com/how-to-plan-a-dinner-party-4163492": "How to Plan a Dinner Party",
                "https://www.thespruceeats.com/potluck-planning-guide-4163493": "Potluck Planning Guide",
                "https://www.thespruceeats.com/school-lunch-ideas-4163494": "School Lunch Ideas",
                "https://www.thespruceeats.com/quick-weeknight-dinners-4163495": "Quick Weeknight Dinners",
                "https://www.thespruceeats.com/thirty-minute-meals-4163496": "Thirty Minute Meals",
                # Seasonal and holiday
                "https://www.thespruceeats.com/thanksgiving-menu-ideas-4163497": "Thanksgiving Menu Ideas",
                "https://www.thespruceeats.com/christmas-dinner-menu-4163498": "Christmas Dinner Menu",
                "https://www.thespruceeats.com/easter-brunch-menu-4163499": "Easter Brunch Menu",
                "https://www.thespruceeats.com/fourth-of-july-menu-4163500": "Fourth of July Menu",
                "https://www.thespruceeats.com/summer-cookout-menu-4163501": "Summer Cookout Menu",
                "https://www.thespruceeats.com/fall-comfort-food-menu-4163502": "Fall Comfort Food Menu",
                "https://www.thespruceeats.com/spring-dinner-menu-4163503": "Spring Dinner Menu",
                "https://www.thespruceeats.com/winter-warming-meals-4163504": "Winter Warming Meals",
                "https://www.thespruceeats.com/valentines-day-dinner-menu-4163505": "Valentines Day Dinner Menu",
                "https://www.thespruceeats.com/super-bowl-party-food-4163506": "Super Bowl Party Food",
                # Dietary planning
                "https://www.thespruceeats.com/vegetarian-meal-plan-4163507": "Vegetarian Meal Plan",
                "https://www.thespruceeats.com/vegan-meal-plan-4163508": "Vegan Meal Plan",
                "https://www.thespruceeats.com/gluten-free-meal-plan-4163509": "Gluten Free Meal Plan",
                "https://www.thespruceeats.com/low-carb-meal-plan-4163510": "Low Carb Meal Plan",
                "https://www.thespruceeats.com/mediterranean-diet-meal-plan-4163511": "Mediterranean Diet Meal Plan",
                "https://www.thespruceeats.com/keto-meal-plan-4163512": "Keto Meal Plan",
                "https://www.thespruceeats.com/dairy-free-meal-plan-4163513": "Dairy Free Meal Plan",
                "https://www.thespruceeats.com/high-protein-meal-plan-4163514": "High Protein Meal Plan",
                "https://www.thespruceeats.com/family-friendly-meal-plan-4163515": "Family Friendly Meal Plan",
                "https://www.thespruceeats.com/cooking-for-one-guide-4163516": "Cooking for One Guide",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"spruce-eats-{source_key}" if source_key else "spruce-eats"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - The Spruce Eats', ' | The Spruce Eats']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"spruce-eats-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(2.0)

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping spruce-eats/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    SpruceEatsScraper(base, source_key).run()
