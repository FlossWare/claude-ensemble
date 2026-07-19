#!/usr/bin/env python3
"""ESP-IDF documentation scraper (docs.espressif.com).

Covers:
  - Get Started (installation, first project, toolchain)
  - API Reference (peripherals, protocols, system, storage, networking)
  - API Guides (build system, partition tables, bootloader, error handling, etc.)
  - HW Reference
  - Migration Guides

Rate limit: 1.5s between fetches
~300 hardcoded URLs from docs.espressif.com/projects/esp-idf/en/stable/esp32/
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper

BASE = "https://docs.espressif.com/projects/esp-idf/en/stable/esp32"


class ESP32Scraper(BaseScraper):
    """Scrape ESP-IDF documentation from Espressif."""

    SOURCES = {
        "get-started": {
            "pages": {
                f"{BASE}/get-started/index.html": "Get Started",
                f"{BASE}/get-started/linux-macos-setup.html": "Linux/macOS Setup",
                f"{BASE}/get-started/windows-setup.html": "Windows Setup",
                f"{BASE}/get-started/establish-serial-connection.html": "Establish Serial Connection",
                f"{BASE}/get-started/flashing-troubleshooting.html": "Flashing Troubleshooting",
                f"{BASE}/get-started/vscode-setup.html": "VS Code Setup",
                f"{BASE}/get-started/eclipse-setup.html": "Eclipse Setup",
            },
        },
        "api-reference": {
            "pages": {
                # Peripherals
                f"{BASE}/api-reference/peripherals/index.html": "Peripherals API Overview",
                f"{BASE}/api-reference/peripherals/adc_oneshot.html": "ADC Oneshot",
                f"{BASE}/api-reference/peripherals/adc_continuous.html": "ADC Continuous",
                f"{BASE}/api-reference/peripherals/dac.html": "DAC",
                f"{BASE}/api-reference/peripherals/gpio.html": "GPIO",
                f"{BASE}/api-reference/peripherals/gptimer.html": "GPTimer",
                f"{BASE}/api-reference/peripherals/i2c.html": "I2C",
                f"{BASE}/api-reference/peripherals/i2s.html": "I2S",
                f"{BASE}/api-reference/peripherals/ledc.html": "LEDC (LED Control)",
                f"{BASE}/api-reference/peripherals/mcpwm.html": "MCPWM",
                f"{BASE}/api-reference/peripherals/pcnt.html": "Pulse Counter",
                f"{BASE}/api-reference/peripherals/rmt.html": "RMT",
                f"{BASE}/api-reference/peripherals/sdmmc_host.html": "SDMMC Host",
                f"{BASE}/api-reference/peripherals/sdspi_host.html": "SD SPI Host",
                f"{BASE}/api-reference/peripherals/sigmadelta.html": "Sigma-Delta Modulation",
                f"{BASE}/api-reference/peripherals/spi_master.html": "SPI Master",
                f"{BASE}/api-reference/peripherals/spi_slave.html": "SPI Slave",
                f"{BASE}/api-reference/peripherals/touch_pad.html": "Touch Sensor",
                f"{BASE}/api-reference/peripherals/twai.html": "TWAI (CAN)",
                f"{BASE}/api-reference/peripherals/uart.html": "UART",
                f"{BASE}/api-reference/peripherals/usb_device.html": "USB Device",
                f"{BASE}/api-reference/peripherals/usb_host.html": "USB Host",
                # Protocols
                f"{BASE}/api-reference/protocols/index.html": "Protocols API Overview",
                f"{BASE}/api-reference/protocols/esp_http_client.html": "HTTP Client",
                f"{BASE}/api-reference/protocols/esp_http_server.html": "HTTP Server",
                f"{BASE}/api-reference/protocols/esp_https_server.html": "HTTPS Server",
                f"{BASE}/api-reference/protocols/esp_tls.html": "ESP-TLS",
                f"{BASE}/api-reference/protocols/mqtt.html": "MQTT",
                f"{BASE}/api-reference/protocols/mdns.html": "mDNS",
                f"{BASE}/api-reference/protocols/modbus.html": "Modbus",
                f"{BASE}/api-reference/protocols/esp_websocket_client.html": "WebSocket Client",
                f"{BASE}/api-reference/protocols/icmp_echo.html": "ICMP Echo",
                f"{BASE}/api-reference/protocols/esp_serial_slave_link.html": "Serial Slave Link",
                f"{BASE}/api-reference/protocols/esp_local_ctrl.html": "Local Control",
                # System
                f"{BASE}/api-reference/system/index.html": "System API Overview",
                f"{BASE}/api-reference/system/app_image_format.html": "App Image Format",
                f"{BASE}/api-reference/system/app_trace.html": "Application Tracing",
                f"{BASE}/api-reference/system/console.html": "Console",
                f"{BASE}/api-reference/system/efuse.html": "eFuse Manager",
                f"{BASE}/api-reference/system/esp_err.html": "Error Codes",
                f"{BASE}/api-reference/system/esp_event.html": "Event Loop",
                f"{BASE}/api-reference/system/esp_https_ota.html": "HTTPS OTA Updates",
                f"{BASE}/api-reference/system/esp_timer.html": "High Resolution Timer",
                f"{BASE}/api-reference/system/freertos.html": "FreeRTOS",
                f"{BASE}/api-reference/system/freertos_idf.html": "FreeRTOS (IDF)",
                f"{BASE}/api-reference/system/heap_debug.html": "Heap Memory Debugging",
                f"{BASE}/api-reference/system/intr_alloc.html": "Interrupt Allocation",
                f"{BASE}/api-reference/system/log.html": "Logging",
                f"{BASE}/api-reference/system/mem_alloc.html": "Memory Allocation",
                f"{BASE}/api-reference/system/ota.html": "OTA Updates",
                f"{BASE}/api-reference/system/perfmon.html": "Performance Monitor",
                f"{BASE}/api-reference/system/power_management.html": "Power Management",
                f"{BASE}/api-reference/system/pthread.html": "POSIX Threads",
                f"{BASE}/api-reference/system/random.html": "Random Number Generation",
                f"{BASE}/api-reference/system/sleep_modes.html": "Sleep Modes",
                f"{BASE}/api-reference/system/soc_caps.html": "SoC Capabilities",
                f"{BASE}/api-reference/system/system_time.html": "System Time",
                f"{BASE}/api-reference/system/wdts.html": "Watchdog Timers",
                # Storage
                f"{BASE}/api-reference/storage/index.html": "Storage API Overview",
                f"{BASE}/api-reference/storage/fatfs.html": "FAT Filesystem",
                f"{BASE}/api-reference/storage/mass_mfg.html": "Mass Manufacturing",
                f"{BASE}/api-reference/storage/nvs_flash.html": "NVS Flash",
                f"{BASE}/api-reference/storage/nvs_partition_gen.html": "NVS Partition Generator",
                f"{BASE}/api-reference/storage/sdmmc.html": "SD/MMC Card",
                f"{BASE}/api-reference/storage/spiffs.html": "SPIFFS",
                f"{BASE}/api-reference/storage/vfs.html": "Virtual Filesystem",
                f"{BASE}/api-reference/storage/wear-levelling.html": "Wear Levelling",
                # Networking
                f"{BASE}/api-reference/network/index.html": "Networking API Overview",
                f"{BASE}/api-reference/network/esp_eth.html": "Ethernet",
                f"{BASE}/api-reference/network/esp_netif.html": "ESP-NETIF",
                f"{BASE}/api-reference/network/esp_now.html": "ESP-NOW",
                f"{BASE}/api-reference/network/esp_smartconfig.html": "SmartConfig",
                f"{BASE}/api-reference/network/esp_wifi.html": "Wi-Fi",
            },
        },
        "api-guides": {
            "pages": {
                f"{BASE}/api-guides/index.html": "API Guides Overview",
                f"{BASE}/api-guides/build-system.html": "Build System",
                f"{BASE}/api-guides/partition-tables.html": "Partition Tables",
                f"{BASE}/api-guides/bootloader.html": "Bootloader",
                f"{BASE}/api-guides/error-handling.html": "Error Handling",
                f"{BASE}/api-guides/fatal-errors.html": "Fatal Errors",
                f"{BASE}/api-guides/sleep-modes.html": "Sleep Modes Guide",
                f"{BASE}/api-guides/jtag-debugging/index.html": "JTAG Debugging",
                f"{BASE}/api-guides/performance/speed.html": "Speed Optimization",
                f"{BASE}/api-guides/performance/size.html": "Size Optimization",
                f"{BASE}/api-guides/unit-testing.html": "Unit Testing",
                f"{BASE}/api-guides/wifi.html": "Wi-Fi Driver Guide",
                f"{BASE}/api-guides/wifi-security.html": "Wi-Fi Security",
                f"{BASE}/api-guides/bluetooth.html": "Bluetooth Overview",
                f"{BASE}/api-guides/blufi.html": "BluFi",
                f"{BASE}/api-guides/esp-ble-mesh/ble-mesh-index.html": "BLE Mesh",
                f"{BASE}/api-guides/mesh.html": "ESP-WIFI-MESH",
                f"{BASE}/api-guides/thread.html": "Thread",
                f"{BASE}/api-guides/core_dump.html": "Core Dump",
                f"{BASE}/api-guides/app_trace.html": "Application Tracing",
                f"{BASE}/api-guides/tools/idf-tools.html": "IDF Tools",
                f"{BASE}/api-guides/tools/idf-monitor.html": "IDF Monitor",
                f"{BASE}/api-guides/tools/idf-py.html": "idf.py",
                f"{BASE}/api-guides/tools/idf-docker-image.html": "IDF Docker Image",
                f"{BASE}/api-guides/tools/idf-component-manager.html": "Component Manager",
                f"{BASE}/api-guides/tools/idf-clang-tidy.html": "IDF Clang-Tidy",
                f"{BASE}/api-guides/lwip.html": "lwIP",
                f"{BASE}/api-guides/linker-script-generation.html": "Linker Script Generation",
                f"{BASE}/api-guides/event-handling.html": "Event Handling",
                f"{BASE}/api-guides/flash_psram_config.html": "Flash and PSRAM Config",
                f"{BASE}/api-guides/dfu.html": "DFU Flashing",
                f"{BASE}/api-guides/usb-serial-jtag-console.html": "USB Serial/JTAG Console",
                f"{BASE}/api-guides/startup.html": "Application Startup",
                f"{BASE}/api-guides/memory-types.html": "Memory Types",
                f"{BASE}/api-guides/openthread.html": "OpenThread",
                f"{BASE}/api-guides/coexist.html": "RF Coexistence",
                f"{BASE}/api-guides/external-ram.html": "External RAM",
                f"{BASE}/api-guides/cplusplus.html": "C++ Support",
                f"{BASE}/api-guides/freertos-smp.html": "FreeRTOS SMP Changes",
                f"{BASE}/api-guides/reproducible-builds.html": "Reproducible Builds",
                f"{BASE}/api-guides/hardware-abstraction.html": "Hardware Abstraction",
                f"{BASE}/api-guides/hlinterrupts.html": "High-Level Interrupts",
                f"{BASE}/api-guides/current-consumption-measurement-modules.html": "Current Measurement",
            },
        },
        "hw-reference": {
            "pages": {
                f"{BASE}/hw-reference/index.html": "Hardware Reference",
                f"{BASE}/hw-reference/chip-series-comparison.html": "Chip Series Comparison",
                f"{BASE}/hw-reference/esp32/get-started-devkitc.html": "ESP32-DevKitC",
                f"{BASE}/hw-reference/esp32/get-started-wrover-kit.html": "ESP-WROVER-KIT",
                f"{BASE}/hw-reference/esp32/get-started-pico-kit.html": "ESP32-PICO-KIT",
                f"{BASE}/hw-reference/esp32/get-started-ethernet-kit.html": "ESP32-Ethernet-Kit",
            },
        },
        "migration-guides": {
            "pages": {
                f"{BASE}/migration-guides/index.html": "Migration Guides Overview",
                f"{BASE}/migration-guides/release-5.x/5.0/index.html": "Migration to 5.0",
                f"{BASE}/migration-guides/release-5.x/5.0/peripherals.html": "5.0 Peripherals Migration",
                f"{BASE}/migration-guides/release-5.x/5.0/system.html": "5.0 System Migration",
                f"{BASE}/migration-guides/release-5.x/5.0/protocols.html": "5.0 Protocols Migration",
                f"{BASE}/migration-guides/release-5.x/5.0/storage.html": "5.0 Storage Migration",
                f"{BASE}/migration-guides/release-5.x/5.0/networking.html": "5.0 Networking Migration",
                f"{BASE}/migration-guides/release-5.x/5.0/build-system.html": "5.0 Build System Migration",
                f"{BASE}/migration-guides/release-5.x/5.1/index.html": "Migration to 5.1",
                f"{BASE}/migration-guides/release-5.x/5.1/peripherals.html": "5.1 Peripherals Migration",
                f"{BASE}/migration-guides/release-5.x/5.1/system.html": "5.1 System Migration",
                f"{BASE}/migration-guides/release-5.x/5.2/index.html": "Migration to 5.2",
                f"{BASE}/migration-guides/release-5.x/5.3/index.html": "Migration to 5.3",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"esp32-{source_key}" if source_key else "esp32"
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
            for suffix in [' - ESP-IDF Programming Guide',
                           ' - ESP32 - ESP-IDF',
                           ' - ESP-IDF', ' | Espressif']:
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
                        "category": f"esp32-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)

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
            self.log.info(f"=== Scraping esp32/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ESP32Scraper(base, source_key).run()
