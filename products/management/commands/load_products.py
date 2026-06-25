import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from products.models import Product, Tag


class Command(BaseCommand):
    help = "Loads product data from Data/products_data.csv into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            default=os.path.join(settings.BASE_DIR, 'Data', 'products_data.csv'),
            help='Path to the CSV file (default: Data/products_data.csv)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing products/tags before loading',
        )

    def handle(self, *args, **options):
        csv_path = options['path']

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f"CSV file not found at: {csv_path}"))
            return

        if options['clear']:
            Product.objects.all().delete()
            Tag.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing products and tags."))

        created_count = 0
        skipped_count = 0
        tag_cache = {}  # name -> Tag instance, avoids hitting DB for every repeated tag

        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                product_id = row.get('id', '').strip()
                name = row.get('product_name', '').strip()
                description = row.get('product_description', '').strip()
                category = row.get('category', '').strip()
                tags_raw = row.get('tags', '').strip()

                if not name or not category:
                    skipped_count += 1
                    continue

                # Use the CSV's own id as the primary key so it stays predictable
                product, created = Product.objects.update_or_create(
                    id=product_id,
                    defaults={
                        'product_name': name,
                        'product_description': description,
                        'category': category,
                    },
                )

                # Parse the comma-separated tag string into individual Tag rows
                tag_names = [t.strip().lower() for t in tags_raw.split(',') if t.strip()]
                tag_objects = []
                for tag_name in tag_names:
                    if tag_name not in tag_cache:
                        tag_obj, _ = Tag.objects.get_or_create(name=tag_name)
                        tag_cache[tag_name] = tag_obj
                    tag_objects.append(tag_cache[tag_name])

                product.tags.set(tag_objects)

                if created:
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. {created_count} products loaded, {skipped_count} rows skipped, "
            f"{Tag.objects.count()} unique tags in database."
        ))