#!/usr/bin/env python3
"""Zephyr RTOS documentation scraper.

Covers:
  - Getting Started: installation, environment setup, first application
  - Kernel: threads, scheduling, memory, synchronization, data passing
  - Hardware: supported boards, SoCs, shields
  - Networking: TCP/IP stack, sockets, MQTT, CoAP, LwM2M
  - Bluetooth: BLE, Mesh, host, controller
  - Drivers: device model, GPIO, SPI, I2C, UART, ADC, PWM
  - Build System: west, CMake, Kconfig, Devicetree
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class ZephyrScraper(BaseScraper):
    """Scrape Zephyr RTOS official documentation."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://docs.zephyrproject.org/latest/introduction/index.html": "Zephyr Introduction",
                "https://docs.zephyrproject.org/latest/develop/getting_started/index.html": "Getting Started Guide",
                "https://docs.zephyrproject.org/latest/develop/env_vars.html": "Environment Variables",
                "https://docs.zephyrproject.org/latest/develop/west/index.html": "West (Zephyr Meta-Tool)",
                "https://docs.zephyrproject.org/latest/develop/west/install.html": "Installing West",
                "https://docs.zephyrproject.org/latest/develop/west/basics.html": "West Basics",
                "https://docs.zephyrproject.org/latest/develop/west/workspaces.html": "West Workspaces",
                "https://docs.zephyrproject.org/latest/develop/application/index.html": "Application Development",
                "https://docs.zephyrproject.org/latest/samples/index.html": "Samples and Demos",
            },
        },
        "kernel": {
            "pages": {
                "https://docs.zephyrproject.org/latest/kernel/services/index.html": "Kernel Services",
                "https://docs.zephyrproject.org/latest/kernel/services/threads/index.html": "Threads",
                "https://docs.zephyrproject.org/latest/kernel/services/scheduling/index.html": "Scheduling",
                "https://docs.zephyrproject.org/latest/kernel/services/interrupts.html": "Interrupts",
                "https://docs.zephyrproject.org/latest/kernel/services/synchronization/semaphores.html": "Semaphores",
                "https://docs.zephyrproject.org/latest/kernel/services/synchronization/mutexes.html": "Mutexes",
                "https://docs.zephyrproject.org/latest/kernel/services/synchronization/condvar.html": "Condition Variables",
                "https://docs.zephyrproject.org/latest/kernel/services/synchronization/events.html": "Events",
                "https://docs.zephyrproject.org/latest/kernel/services/data_passing/message_queues.html": "Message Queues",
                "https://docs.zephyrproject.org/latest/kernel/services/data_passing/mailboxes.html": "Mailboxes",
                "https://docs.zephyrproject.org/latest/kernel/services/data_passing/pipes.html": "Pipes",
                "https://docs.zephyrproject.org/latest/kernel/services/data_passing/fifos.html": "FIFOs",
                "https://docs.zephyrproject.org/latest/kernel/services/data_passing/lifos.html": "LIFOs",
                "https://docs.zephyrproject.org/latest/kernel/services/data_passing/stacks.html": "Stacks",
                "https://docs.zephyrproject.org/latest/kernel/services/timing/clocks.html": "Clocks",
                "https://docs.zephyrproject.org/latest/kernel/services/timing/timers.html": "Timers",
                "https://docs.zephyrproject.org/latest/kernel/services/other/atomic.html": "Atomic Services",
                "https://docs.zephyrproject.org/latest/kernel/services/other/float.html": "Floating Point Services",
                "https://docs.zephyrproject.org/latest/kernel/memory_management/index.html": "Memory Management",
                "https://docs.zephyrproject.org/latest/kernel/memory_management/heap.html": "Heap Memory Pool",
                "https://docs.zephyrproject.org/latest/kernel/memory_management/slabs.html": "Memory Slabs",
                "https://docs.zephyrproject.org/latest/kernel/usermode/index.html": "User Mode",
            },
        },
        "hardware": {
            "pages": {
                "https://docs.zephyrproject.org/latest/boards/index.html": "Supported Boards",
                "https://docs.zephyrproject.org/latest/hardware/porting/index.html": "Porting Guide",
                "https://docs.zephyrproject.org/latest/hardware/porting/board_porting.html": "Board Porting",
                "https://docs.zephyrproject.org/latest/hardware/porting/arch.html": "Architecture Porting",
                "https://docs.zephyrproject.org/latest/hardware/shields/index.html": "Shields",
                "https://docs.zephyrproject.org/latest/hardware/emulator/index.html": "Emulators",
            },
        },
        "networking": {
            "pages": {
                "https://docs.zephyrproject.org/latest/connectivity/networking/index.html": "Networking Overview",
                "https://docs.zephyrproject.org/latest/connectivity/networking/api/index.html": "Networking API",
                "https://docs.zephyrproject.org/latest/connectivity/networking/api/net_if.html": "Network Interface",
                "https://docs.zephyrproject.org/latest/connectivity/networking/api/sockets.html": "BSD Sockets",
                "https://docs.zephyrproject.org/latest/connectivity/networking/api/mqtt.html": "MQTT",
                "https://docs.zephyrproject.org/latest/connectivity/networking/api/coap.html": "CoAP",
                "https://docs.zephyrproject.org/latest/connectivity/networking/api/lwm2m.html": "LwM2M",
                "https://docs.zephyrproject.org/latest/connectivity/networking/api/http.html": "HTTP",
                "https://docs.zephyrproject.org/latest/connectivity/networking/api/dns.html": "DNS Resolve",
                "https://docs.zephyrproject.org/latest/connectivity/networking/api/net_config.html": "Network Configuration",
            },
        },
        "bluetooth": {
            "pages": {
                "https://docs.zephyrproject.org/latest/connectivity/bluetooth/index.html": "Bluetooth Overview",
                "https://docs.zephyrproject.org/latest/connectivity/bluetooth/api/index.html": "Bluetooth API Reference",
                "https://docs.zephyrproject.org/latest/connectivity/bluetooth/api/gap.html": "GAP (Generic Access Profile)",
                "https://docs.zephyrproject.org/latest/connectivity/bluetooth/api/gatt.html": "GATT (Generic Attribute Profile)",
                "https://docs.zephyrproject.org/latest/connectivity/bluetooth/api/connection.html": "Connection Management",
                "https://docs.zephyrproject.org/latest/connectivity/bluetooth/api/mesh.html": "Bluetooth Mesh",
                "https://docs.zephyrproject.org/latest/connectivity/bluetooth/bluetooth-arch.html": "Bluetooth Architecture",
                "https://docs.zephyrproject.org/latest/connectivity/bluetooth/bluetooth-qual.html": "Bluetooth Qualification",
            },
        },
        "drivers": {
            "pages": {
                "https://docs.zephyrproject.org/latest/hardware/peripherals/index.html": "Peripherals Overview",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/gpio.html": "GPIO",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/spi.html": "SPI",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/i2c.html": "I2C",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/uart.html": "UART",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/adc.html": "ADC",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/pwm.html": "PWM",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/sensor.html": "Sensors",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/can.html": "CAN Bus",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/dma.html": "DMA",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/flash.html": "Flash",
                "https://docs.zephyrproject.org/latest/hardware/peripherals/watchdog.html": "Watchdog Timer",
            },
        },
        "build-system": {
            "pages": {
                "https://docs.zephyrproject.org/latest/build/index.html": "Build System Overview",
                "https://docs.zephyrproject.org/latest/build/cmake/index.html": "CMake Build System",
                "https://docs.zephyrproject.org/latest/build/kconfig/index.html": "Kconfig Configuration",
                "https://docs.zephyrproject.org/latest/build/kconfig/setting.html": "Setting Kconfig Values",
                "https://docs.zephyrproject.org/latest/build/dts/index.html": "Devicetree",
                "https://docs.zephyrproject.org/latest/build/dts/intro.html": "Devicetree Introduction",
                "https://docs.zephyrproject.org/latest/build/dts/bindings.html": "Devicetree Bindings",
                "https://docs.zephyrproject.org/latest/build/dts/api-usage.html": "Devicetree API Usage",
                "https://docs.zephyrproject.org/latest/develop/west/build-flash-debug.html": "West Build Flash Debug",
                "https://docs.zephyrproject.org/latest/develop/west/manifest.html": "West Manifest",
                "https://docs.zephyrproject.org/latest/develop/west/extensions.html": "West Extensions",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"zephyr-{source_key}" if source_key else "zephyr"
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
            for suffix in [' — Zephyr Project Documentation',
                           ' - Zephyr Project', ' | Zephyr']:
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
                        "category": f"zephyr-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)  # Rate limit

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
            self.log.info(f"=== Scraping zephyr/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ZephyrScraper(base, source_key).run()
