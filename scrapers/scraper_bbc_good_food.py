#!/usr/bin/env python3
"""BBC Good Food scraper.

Covers:
  - Recipes (cakes, chicken, pasta, vegetarian, vegan, healthy, etc.)
  - How-to guides (cooking techniques, kitchen tips, food prep)
  - Nutrition guides (health, diet plans, ingredient benefits)
  - Collections (seasonal, holiday, weekend, family, entertaining)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


RATE_LIMIT = 2.0


class BBCGoodFoodScraper(BaseScraper):
    """Scrape BBC Good Food recipes, guides, and collections."""

    SOURCES = {
        "recipes": {
            "pages": {
                # Cakes & baking
                "https://www.bbcgoodfood.com/recipes/classic-victoria-sponge": "Classic Victoria Sponge",
                "https://www.bbcgoodfood.com/recipes/best-ever-chocolate-brownies": "Best Ever Chocolate Brownies",
                "https://www.bbcgoodfood.com/recipes/classic-scones": "Classic Scones",
                "https://www.bbcgoodfood.com/recipes/banana-bread": "Banana Bread",
                "https://www.bbcgoodfood.com/recipes/lemon-drizzle-cake": "Lemon Drizzle Cake",
                "https://www.bbcgoodfood.com/recipes/carrot-cake": "Carrot Cake",
                "https://www.bbcgoodfood.com/recipes/chocolate-cake": "Chocolate Cake",
                "https://www.bbcgoodfood.com/recipes/red-velvet-cake": "Red Velvet Cake",
                "https://www.bbcgoodfood.com/recipes/coffee-walnut-cake": "Coffee & Walnut Cake",
                "https://www.bbcgoodfood.com/recipes/easy-chocolate-fudge-cake": "Easy Chocolate Fudge Cake",
                "https://www.bbcgoodfood.com/recipes/mary-berrys-lemon-swiss-roll": "Lemon Swiss Roll",
                "https://www.bbcgoodfood.com/recipes/sticky-toffee-pudding": "Sticky Toffee Pudding",
                "https://www.bbcgoodfood.com/recipes/classic-apple-crumble": "Classic Apple Crumble",
                "https://www.bbcgoodfood.com/recipes/treacle-tart": "Treacle Tart",
                "https://www.bbcgoodfood.com/recipes/easy-bread-butter-pudding": "Bread & Butter Pudding",
                # Chicken
                "https://www.bbcgoodfood.com/recipes/easy-chicken-fajitas": "Easy Chicken Fajitas",
                "https://www.bbcgoodfood.com/recipes/chicken-tikka-masala": "Chicken Tikka Masala",
                "https://www.bbcgoodfood.com/recipes/classic-roast-chicken": "Classic Roast Chicken",
                "https://www.bbcgoodfood.com/recipes/chicken-stir-fry": "Chicken Stir Fry",
                "https://www.bbcgoodfood.com/recipes/chicken-curry": "Chicken Curry",
                "https://www.bbcgoodfood.com/recipes/chicken-pie": "Chicken Pie",
                "https://www.bbcgoodfood.com/recipes/chicken-casserole": "Chicken Casserole",
                "https://www.bbcgoodfood.com/recipes/chicken-soup": "Chicken Soup",
                "https://www.bbcgoodfood.com/recipes/lemon-chicken": "Lemon Chicken",
                "https://www.bbcgoodfood.com/recipes/butter-chicken": "Butter Chicken",
                "https://www.bbcgoodfood.com/recipes/chicken-satay": "Chicken Satay",
                "https://www.bbcgoodfood.com/recipes/chicken-katsu-curry": "Chicken Katsu Curry",
                "https://www.bbcgoodfood.com/recipes/chicken-cacciatore": "Chicken Cacciatore",
                "https://www.bbcgoodfood.com/recipes/sticky-chicken-thighs": "Sticky Chicken Thighs",
                "https://www.bbcgoodfood.com/recipes/chicken-noodle-soup": "Chicken Noodle Soup",
                # Pasta
                "https://www.bbcgoodfood.com/recipes/spaghetti-bolognese": "Spaghetti Bolognese",
                "https://www.bbcgoodfood.com/recipes/easy-lasagne": "Easy Lasagne",
                "https://www.bbcgoodfood.com/recipes/spaghetti-carbonara": "Spaghetti Carbonara",
                "https://www.bbcgoodfood.com/recipes/macaroni-cheese": "Macaroni Cheese",
                "https://www.bbcgoodfood.com/recipes/pasta-bake": "Pasta Bake",
                "https://www.bbcgoodfood.com/recipes/penne-arrabbiata": "Penne Arrabbiata",
                "https://www.bbcgoodfood.com/recipes/creamy-mushroom-pasta": "Creamy Mushroom Pasta",
                "https://www.bbcgoodfood.com/recipes/prawn-linguine": "Prawn Linguine",
                "https://www.bbcgoodfood.com/recipes/tuna-pasta-bake": "Tuna Pasta Bake",
                "https://www.bbcgoodfood.com/recipes/pasta-primavera": "Pasta Primavera",
                # Vegetarian
                "https://www.bbcgoodfood.com/recipes/vegetable-lasagne": "Vegetable Lasagne",
                "https://www.bbcgoodfood.com/recipes/mushroom-risotto": "Mushroom Risotto",
                "https://www.bbcgoodfood.com/recipes/vegetable-curry": "Vegetable Curry",
                "https://www.bbcgoodfood.com/recipes/halloumi-salad": "Halloumi Salad",
                "https://www.bbcgoodfood.com/recipes/spinach-ricotta-cannelloni": "Spinach & Ricotta Cannelloni",
                "https://www.bbcgoodfood.com/recipes/aubergine-parmigiana": "Aubergine Parmigiana",
                "https://www.bbcgoodfood.com/recipes/stuffed-peppers": "Stuffed Peppers",
                "https://www.bbcgoodfood.com/recipes/cheese-omelette": "Cheese Omelette",
                "https://www.bbcgoodfood.com/recipes/ratatouille": "Ratatouille",
                "https://www.bbcgoodfood.com/recipes/goats-cheese-tart": "Goats Cheese Tart",
                # Vegan
                "https://www.bbcgoodfood.com/recipes/vegan-chilli": "Vegan Chilli",
                "https://www.bbcgoodfood.com/recipes/vegan-banana-bread": "Vegan Banana Bread",
                "https://www.bbcgoodfood.com/recipes/vegan-curry": "Vegan Curry",
                "https://www.bbcgoodfood.com/recipes/vegan-brownies": "Vegan Brownies",
                "https://www.bbcgoodfood.com/recipes/vegan-pancakes": "Vegan Pancakes",
                "https://www.bbcgoodfood.com/recipes/vegan-shepherd-pie": "Vegan Shepherd's Pie",
                "https://www.bbcgoodfood.com/recipes/vegan-bolognese": "Vegan Bolognese",
                "https://www.bbcgoodfood.com/recipes/vegan-mac-cheese": "Vegan Mac & Cheese",
                "https://www.bbcgoodfood.com/recipes/vegan-stir-fry": "Vegan Stir Fry",
                "https://www.bbcgoodfood.com/recipes/vegan-lasagne": "Vegan Lasagne",
                # Healthy
                "https://www.bbcgoodfood.com/recipes/healthy-chicken-salad": "Healthy Chicken Salad",
                "https://www.bbcgoodfood.com/recipes/healthy-salmon-bowl": "Healthy Salmon Bowl",
                "https://www.bbcgoodfood.com/recipes/healthy-turkey-meatballs": "Healthy Turkey Meatballs",
                "https://www.bbcgoodfood.com/recipes/quinoa-salad": "Quinoa Salad",
                "https://www.bbcgoodfood.com/recipes/grilled-salmon-with-vegetables": "Grilled Salmon with Vegetables",
                "https://www.bbcgoodfood.com/recipes/healthy-fish-pie": "Healthy Fish Pie",
                "https://www.bbcgoodfood.com/recipes/lentil-soup": "Lentil Soup",
                "https://www.bbcgoodfood.com/recipes/sweet-potato-soup": "Sweet Potato Soup",
                "https://www.bbcgoodfood.com/recipes/healthy-pasta-salad": "Healthy Pasta Salad",
                "https://www.bbcgoodfood.com/recipes/low-calorie-chicken-dinner": "Low Calorie Chicken Dinner",
                # Quick & easy
                "https://www.bbcgoodfood.com/recipes/easy-pancakes": "Easy Pancakes",
                "https://www.bbcgoodfood.com/recipes/classic-fish-chips": "Classic Fish & Chips",
                "https://www.bbcgoodfood.com/recipes/scrambled-eggs": "Scrambled Eggs",
                "https://www.bbcgoodfood.com/recipes/cheese-toastie": "Cheese Toastie",
                "https://www.bbcgoodfood.com/recipes/omelette": "Omelette",
                "https://www.bbcgoodfood.com/recipes/beans-on-toast": "Beans on Toast",
                "https://www.bbcgoodfood.com/recipes/egg-fried-rice": "Egg Fried Rice",
                "https://www.bbcgoodfood.com/recipes/quick-chilli": "Quick Chilli",
                "https://www.bbcgoodfood.com/recipes/15-minute-pasta": "15 Minute Pasta",
                "https://www.bbcgoodfood.com/recipes/quick-tomato-soup": "Quick Tomato Soup",
                # Budget
                "https://www.bbcgoodfood.com/recipes/cheap-chicken-traybake": "Cheap Chicken Traybake",
                "https://www.bbcgoodfood.com/recipes/budget-bolognese": "Budget Bolognese",
                "https://www.bbcgoodfood.com/recipes/sausage-casserole": "Sausage Casserole",
                "https://www.bbcgoodfood.com/recipes/corned-beef-hash": "Corned Beef Hash",
                "https://www.bbcgoodfood.com/recipes/bean-chilli": "Bean Chilli",
                "https://www.bbcgoodfood.com/recipes/budget-fish-cakes": "Budget Fish Cakes",
                "https://www.bbcgoodfood.com/recipes/cheap-pasta-bake": "Cheap Pasta Bake",
                "https://www.bbcgoodfood.com/recipes/jacket-potatoes-with-beans": "Jacket Potatoes with Beans",
                "https://www.bbcgoodfood.com/recipes/budget-fried-rice": "Budget Fried Rice",
                "https://www.bbcgoodfood.com/recipes/easy-egg-muffins": "Easy Egg Muffins",
                # Comfort food
                "https://www.bbcgoodfood.com/recipes/shepherds-pie": "Shepherd's Pie",
                "https://www.bbcgoodfood.com/recipes/cottage-pie": "Cottage Pie",
                "https://www.bbcgoodfood.com/recipes/beef-stew": "Beef Stew",
                "https://www.bbcgoodfood.com/recipes/toad-in-the-hole": "Toad in the Hole",
                "https://www.bbcgoodfood.com/recipes/bangers-and-mash": "Bangers and Mash",
                "https://www.bbcgoodfood.com/recipes/slow-cooker-pulled-pork": "Slow Cooker Pulled Pork",
                "https://www.bbcgoodfood.com/recipes/beef-bourguignon": "Beef Bourguignon",
                "https://www.bbcgoodfood.com/recipes/fish-pie": "Fish Pie",
                "https://www.bbcgoodfood.com/recipes/lamb-hotpot": "Lamb Hotpot",
                "https://www.bbcgoodfood.com/recipes/chicken-and-leek-pie": "Chicken & Leek Pie",
                # Desserts
                "https://www.bbcgoodfood.com/recipes/chocolate-mousse": "Chocolate Mousse",
                "https://www.bbcgoodfood.com/recipes/panna-cotta": "Panna Cotta",
                "https://www.bbcgoodfood.com/recipes/tiramisu": "Tiramisu",
                "https://www.bbcgoodfood.com/recipes/creme-brulee": "Creme Brulee",
                "https://www.bbcgoodfood.com/recipes/eton-mess": "Eton Mess",
                "https://www.bbcgoodfood.com/recipes/chocolate-fondant": "Chocolate Fondant",
                "https://www.bbcgoodfood.com/recipes/rice-pudding": "Rice Pudding",
                "https://www.bbcgoodfood.com/recipes/lemon-posset": "Lemon Posset",
                "https://www.bbcgoodfood.com/recipes/banoffee-pie": "Banoffee Pie",
                "https://www.bbcgoodfood.com/recipes/cheesecake": "Cheesecake",
                # Soups
                "https://www.bbcgoodfood.com/recipes/tomato-soup": "Tomato Soup",
                "https://www.bbcgoodfood.com/recipes/leek-potato-soup": "Leek & Potato Soup",
                "https://www.bbcgoodfood.com/recipes/butternut-squash-soup": "Butternut Squash Soup",
                "https://www.bbcgoodfood.com/recipes/french-onion-soup": "French Onion Soup",
                "https://www.bbcgoodfood.com/recipes/minestrone-soup": "Minestrone Soup",
                "https://www.bbcgoodfood.com/recipes/pea-mint-soup": "Pea & Mint Soup",
                "https://www.bbcgoodfood.com/recipes/mushroom-soup": "Mushroom Soup",
                "https://www.bbcgoodfood.com/recipes/broccoli-stilton-soup": "Broccoli & Stilton Soup",
                "https://www.bbcgoodfood.com/recipes/carrot-coriander-soup": "Carrot & Coriander Soup",
                "https://www.bbcgoodfood.com/recipes/chicken-sweetcorn-soup": "Chicken & Sweetcorn Soup",
                # Salads
                "https://www.bbcgoodfood.com/recipes/caesar-salad": "Caesar Salad",
                "https://www.bbcgoodfood.com/recipes/greek-salad": "Greek Salad",
                "https://www.bbcgoodfood.com/recipes/nicoise-salad": "Nicoise Salad",
                "https://www.bbcgoodfood.com/recipes/coleslaw": "Coleslaw",
                "https://www.bbcgoodfood.com/recipes/waldorf-salad": "Waldorf Salad",
                "https://www.bbcgoodfood.com/recipes/potato-salad": "Potato Salad",
                "https://www.bbcgoodfood.com/recipes/tabbouleh": "Tabbouleh",
                "https://www.bbcgoodfood.com/recipes/caprese-salad": "Caprese Salad",
                "https://www.bbcgoodfood.com/recipes/cobb-salad": "Cobb Salad",
                "https://www.bbcgoodfood.com/recipes/thai-beef-salad": "Thai Beef Salad",
                # Breakfast
                "https://www.bbcgoodfood.com/recipes/full-english-breakfast": "Full English Breakfast",
                "https://www.bbcgoodfood.com/recipes/eggs-benedict": "Eggs Benedict",
                "https://www.bbcgoodfood.com/recipes/porridge": "Porridge",
                "https://www.bbcgoodfood.com/recipes/granola": "Granola",
                "https://www.bbcgoodfood.com/recipes/avocado-on-toast": "Avocado on Toast",
                "https://www.bbcgoodfood.com/recipes/french-toast": "French Toast",
                "https://www.bbcgoodfood.com/recipes/shakshuka": "Shakshuka",
                "https://www.bbcgoodfood.com/recipes/american-pancakes": "American Pancakes",
                "https://www.bbcgoodfood.com/recipes/overnight-oats": "Overnight Oats",
                "https://www.bbcgoodfood.com/recipes/breakfast-burrito": "Breakfast Burrito",
                # Dinner party
                "https://www.bbcgoodfood.com/recipes/beef-wellington": "Beef Wellington",
                "https://www.bbcgoodfood.com/recipes/rack-of-lamb": "Rack of Lamb",
                "https://www.bbcgoodfood.com/recipes/duck-breast": "Duck Breast",
                "https://www.bbcgoodfood.com/recipes/lobster-thermidor": "Lobster Thermidor",
                "https://www.bbcgoodfood.com/recipes/sea-bass-with-lemon": "Sea Bass with Lemon",
                "https://www.bbcgoodfood.com/recipes/lamb-shank": "Lamb Shank",
                "https://www.bbcgoodfood.com/recipes/prawn-cocktail": "Prawn Cocktail",
                "https://www.bbcgoodfood.com/recipes/coq-au-vin": "Coq au Vin",
                "https://www.bbcgoodfood.com/recipes/beef-stroganoff": "Beef Stroganoff",
                "https://www.bbcgoodfood.com/recipes/salmon-en-croute": "Salmon en Croute",
            },
        },
        "how-to": {
            "pages": {
                # Cooking techniques
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-bread": "How to Make Bread",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-pastry": "How to Make Pastry",
                "https://www.bbcgoodfood.com/howto/guide/how-to-cook-rice-perfectly": "How to Cook Rice Perfectly",
                "https://www.bbcgoodfood.com/howto/guide/how-to-roast-a-chicken": "How to Roast a Chicken",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-gravy": "How to Make Gravy",
                "https://www.bbcgoodfood.com/howto/guide/how-to-poach-an-egg": "How to Poach an Egg",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-stock": "How to Make Stock",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-white-sauce": "How to Make White Sauce",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-yorkshire-puddings": "How to Make Yorkshire Puddings",
                "https://www.bbcgoodfood.com/howto/guide/how-to-cook-steak": "How to Cook Steak",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-omelette": "How to Make an Omelette",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-meringue": "How to Make Meringue",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-custard": "How to Make Custard",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-pizza-dough": "How to Make Pizza Dough",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-pancakes": "How to Make Pancakes",
                "https://www.bbcgoodfood.com/howto/guide/how-to-cook-pasta": "How to Cook Pasta",
                "https://www.bbcgoodfood.com/howto/guide/how-to-caramelise-onions": "How to Caramelise Onions",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-jam": "How to Make Jam",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-chutney": "How to Make Chutney",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-soup": "How to Make Soup",
                # Kitchen tips
                "https://www.bbcgoodfood.com/howto/guide/kitchen-knives-guide": "Kitchen Knives Guide",
                "https://www.bbcgoodfood.com/howto/guide/how-to-sharpen-knives": "How to Sharpen Knives",
                "https://www.bbcgoodfood.com/howto/guide/essential-kitchen-equipment": "Essential Kitchen Equipment",
                "https://www.bbcgoodfood.com/howto/guide/how-to-organise-your-kitchen": "How to Organise Your Kitchen",
                "https://www.bbcgoodfood.com/howto/guide/food-storage-guide": "Food Storage Guide",
                "https://www.bbcgoodfood.com/howto/guide/freezing-food-guide": "Freezing Food Guide",
                "https://www.bbcgoodfood.com/howto/guide/how-to-reduce-food-waste": "How to Reduce Food Waste",
                "https://www.bbcgoodfood.com/howto/guide/meal-prep-guide": "Meal Prep Guide",
                "https://www.bbcgoodfood.com/howto/guide/batch-cooking-guide": "Batch Cooking Guide",
                "https://www.bbcgoodfood.com/howto/guide/how-to-season-a-cast-iron-pan": "How to Season a Cast Iron Pan",
                # Food prep
                "https://www.bbcgoodfood.com/howto/guide/how-to-chop-an-onion": "How to Chop an Onion",
                "https://www.bbcgoodfood.com/howto/guide/how-to-peel-tomatoes": "How to Peel Tomatoes",
                "https://www.bbcgoodfood.com/howto/guide/how-to-prepare-avocado": "How to Prepare Avocado",
                "https://www.bbcgoodfood.com/howto/guide/how-to-prepare-prawns": "How to Prepare Prawns",
                "https://www.bbcgoodfood.com/howto/guide/how-to-segment-an-orange": "How to Segment an Orange",
                "https://www.bbcgoodfood.com/howto/guide/how-to-prepare-asparagus": "How to Prepare Asparagus",
                "https://www.bbcgoodfood.com/howto/guide/how-to-prepare-artichokes": "How to Prepare Artichokes",
                "https://www.bbcgoodfood.com/howto/guide/how-to-prepare-butternut-squash": "How to Prepare Butternut Squash",
                "https://www.bbcgoodfood.com/howto/guide/how-to-prepare-mango": "How to Prepare Mango",
                "https://www.bbcgoodfood.com/howto/guide/how-to-prepare-pomegranate": "How to Prepare Pomegranate",
                # Baking guides
                "https://www.bbcgoodfood.com/howto/guide/how-to-line-a-cake-tin": "How to Line a Cake Tin",
                "https://www.bbcgoodfood.com/howto/guide/how-to-cream-butter-and-sugar": "How to Cream Butter and Sugar",
                "https://www.bbcgoodfood.com/howto/guide/how-to-fold-in-flour": "How to Fold in Flour",
                "https://www.bbcgoodfood.com/howto/guide/how-to-knead-dough": "How to Knead Dough",
                "https://www.bbcgoodfood.com/howto/guide/how-to-blind-bake-pastry": "How to Blind Bake Pastry",
                "https://www.bbcgoodfood.com/howto/guide/how-to-temper-chocolate": "How to Temper Chocolate",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-icing": "How to Make Icing",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-sourdough-starter": "How to Make Sourdough Starter",
                "https://www.bbcgoodfood.com/howto/guide/how-to-pipe-icing": "How to Pipe Icing",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-choux-pastry": "How to Make Choux Pastry",
                # Preserving
                "https://www.bbcgoodfood.com/howto/guide/how-to-pickle-vegetables": "How to Pickle Vegetables",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-marmalade": "How to Make Marmalade",
                "https://www.bbcgoodfood.com/howto/guide/how-to-dry-herbs": "How to Dry Herbs",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-preserved-lemons": "How to Make Preserved Lemons",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-kimchi": "How to Make Kimchi",
                "https://www.bbcgoodfood.com/howto/guide/how-to-ferment-vegetables": "How to Ferment Vegetables",
                "https://www.bbcgoodfood.com/howto/guide/how-to-bottle-fruit": "How to Bottle Fruit",
                "https://www.bbcgoodfood.com/howto/guide/how-to-cure-salmon": "How to Cure Salmon",
                "https://www.bbcgoodfood.com/howto/guide/how-to-make-sauerkraut": "How to Make Sauerkraut",
                "https://www.bbcgoodfood.com/howto/guide/how-to-smoke-food-at-home": "How to Smoke Food at Home",
            },
        },
        "nutrition": {
            "pages": {
                # Health guides
                "https://www.bbcgoodfood.com/howto/guide/what-are-superfoods": "What Are Superfoods",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-salmon": "Health Benefits of Salmon",
                "https://www.bbcgoodfood.com/howto/guide/top-10-healthy-breakfast-ideas": "Top 10 Healthy Breakfast Ideas",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-avocado": "Health Benefits of Avocado",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-turmeric": "Health Benefits of Turmeric",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-ginger": "Health Benefits of Ginger",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-blueberries": "Health Benefits of Blueberries",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-oats": "Health Benefits of Oats",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-spinach": "Health Benefits of Spinach",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-eggs": "Health Benefits of Eggs",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-green-tea": "Health Benefits of Green Tea",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-nuts": "Health Benefits of Nuts",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-olive-oil": "Health Benefits of Olive Oil",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-dark-chocolate": "Health Benefits of Dark Chocolate",
                "https://www.bbcgoodfood.com/howto/guide/health-benefits-of-garlic": "Health Benefits of Garlic",
                # Diet plans
                "https://www.bbcgoodfood.com/howto/guide/what-is-the-mediterranean-diet": "What Is the Mediterranean Diet",
                "https://www.bbcgoodfood.com/howto/guide/what-is-the-5-2-diet": "What Is the 5:2 Diet",
                "https://www.bbcgoodfood.com/howto/guide/what-is-a-plant-based-diet": "What Is a Plant-Based Diet",
                "https://www.bbcgoodfood.com/howto/guide/what-is-the-keto-diet": "What Is the Keto Diet",
                "https://www.bbcgoodfood.com/howto/guide/what-is-intermittent-fasting": "What Is Intermittent Fasting",
                "https://www.bbcgoodfood.com/howto/guide/what-is-a-low-fodmap-diet": "What Is a Low-FODMAP Diet",
                "https://www.bbcgoodfood.com/howto/guide/what-is-the-paleo-diet": "What Is the Paleo Diet",
                "https://www.bbcgoodfood.com/howto/guide/what-is-a-gluten-free-diet": "What Is a Gluten-Free Diet",
                "https://www.bbcgoodfood.com/howto/guide/what-is-a-low-carb-diet": "What Is a Low-Carb Diet",
                "https://www.bbcgoodfood.com/howto/guide/what-is-a-high-protein-diet": "What Is a High-Protein Diet",
                # Ingredient benefits
                "https://www.bbcgoodfood.com/howto/guide/benefits-of-probiotics": "Benefits of Probiotics",
                "https://www.bbcgoodfood.com/howto/guide/benefits-of-omega-3": "Benefits of Omega-3",
                "https://www.bbcgoodfood.com/howto/guide/benefits-of-vitamin-d": "Benefits of Vitamin D",
                "https://www.bbcgoodfood.com/howto/guide/benefits-of-iron-rich-foods": "Benefits of Iron-Rich Foods",
                "https://www.bbcgoodfood.com/howto/guide/benefits-of-fibre": "Benefits of Fibre",
                "https://www.bbcgoodfood.com/howto/guide/benefits-of-antioxidants": "Benefits of Antioxidants",
                "https://www.bbcgoodfood.com/howto/guide/benefits-of-zinc": "Benefits of Zinc",
                "https://www.bbcgoodfood.com/howto/guide/benefits-of-magnesium": "Benefits of Magnesium",
                "https://www.bbcgoodfood.com/howto/guide/benefits-of-vitamin-c": "Benefits of Vitamin C",
                "https://www.bbcgoodfood.com/howto/guide/benefits-of-calcium": "Benefits of Calcium",
                # Seasonal eating
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-january": "What's in Season: January",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-february": "What's in Season: February",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-march": "What's in Season: March",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-april": "What's in Season: April",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-may": "What's in Season: May",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-june": "What's in Season: June",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-july": "What's in Season: July",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-august": "What's in Season: August",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-september": "What's in Season: September",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-october": "What's in Season: October",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-november": "What's in Season: November",
                "https://www.bbcgoodfood.com/howto/guide/whats-in-season-december": "What's in Season: December",
            },
        },
        "collections": {
            "pages": {
                # Seasonal
                "https://www.bbcgoodfood.com/recipes/collection/spring-recipes": "Spring Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/summer-recipes": "Summer Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/autumn-recipes": "Autumn Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/winter-recipes": "Winter Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/january-recipes": "January Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/february-recipes": "February Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/march-recipes": "March Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/april-recipes": "April Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/may-recipes": "May Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/june-recipes": "June Recipes",
                # Holiday
                "https://www.bbcgoodfood.com/recipes/collection/christmas-dinner": "Christmas Dinner",
                "https://www.bbcgoodfood.com/recipes/collection/christmas-baking": "Christmas Baking",
                "https://www.bbcgoodfood.com/recipes/collection/christmas-cake-recipes": "Christmas Cake Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/easter-recipes": "Easter Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/halloween-recipes": "Halloween Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/bonfire-night-recipes": "Bonfire Night Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/valentines-day-recipes": "Valentine's Day Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/pancake-day-recipes": "Pancake Day Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/mothers-day-recipes": "Mother's Day Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/fathers-day-recipes": "Father's Day Recipes",
                # Weekend
                "https://www.bbcgoodfood.com/recipes/collection/sunday-lunch-recipes": "Sunday Lunch Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/easy-weeknight-dinners": "Easy Weeknight Dinners",
                "https://www.bbcgoodfood.com/recipes/collection/brunch-recipes": "Brunch Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/saturday-night-recipes": "Saturday Night Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/lazy-weekend-recipes": "Lazy Weekend Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/slow-cooker-recipes": "Slow Cooker Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/one-pot-recipes": "One Pot Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/traybake-recipes": "Traybake Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/batch-cooking-recipes": "Batch Cooking Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/freezable-recipes": "Freezable Recipes",
                # Family
                "https://www.bbcgoodfood.com/recipes/collection/family-meal-recipes": "Family Meal Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/kids-cooking-recipes": "Kids Cooking Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/lunchbox-recipes": "Lunchbox Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/toddler-recipes": "Toddler Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/baby-food-recipes": "Baby Food Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/after-school-snack-recipes": "After School Snack Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/packed-lunch-ideas": "Packed Lunch Ideas",
                "https://www.bbcgoodfood.com/recipes/collection/fussy-eater-recipes": "Fussy Eater Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/hidden-veg-recipes": "Hidden Veg Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/cooking-with-kids": "Cooking with Kids",
                # Entertaining
                "https://www.bbcgoodfood.com/recipes/collection/dinner-party-recipes": "Dinner Party Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/canape-recipes": "Canape Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/bbq-recipes": "BBQ Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/picnic-recipes": "Picnic Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/afternoon-tea-recipes": "Afternoon Tea Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/buffet-recipes": "Buffet Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/cocktail-party-recipes": "Cocktail Party Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/starter-recipes": "Starter Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/side-dish-recipes": "Side Dish Recipes",
                "https://www.bbcgoodfood.com/recipes/collection/sharing-platter-recipes": "Sharing Platter Recipes",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"bbc-good-food-{source_key}" if source_key else "bbc-good-food"
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
            for suffix in [' recipe | BBC Good Food', ' | BBC Good Food', ' - BBC Good Food']:
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
                        "category": f"bbc-good-food-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(RATE_LIMIT)

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
            self.log.info(f"=== Scraping bbc-good-food/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    BBCGoodFoodScraper(base, source_key).run()
