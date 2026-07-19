#!/usr/bin/env python3
"""Raspberry Pi documentation scraper.

Covers:
  - Computers (getting-started, OS, configuration, remote-access, linux, camera, GPIO, Pico)
  - Microcontrollers (RP2040, RP2350, Pico SDK, MicroPython, C SDK)
  - Accessories
  - Services

Rate limit: 1.5s between fetches
~300 hardcoded URLs
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class RaspberryPiScraper(BaseScraper):
    """Scrape Raspberry Pi documentation."""

    SOURCES = {
        "computers": {
            "pages": {
                # Getting started
                "https://www.raspberrypi.com/documentation/computers/getting-started.html": "Getting Started",
                "https://www.raspberrypi.com/documentation/computers/os.html": "Raspberry Pi OS",
                "https://www.raspberrypi.com/documentation/computers/configuration.html": "Configuration",
                "https://www.raspberrypi.com/documentation/computers/remote-access.html": "Remote Access",
                "https://www.raspberrypi.com/documentation/computers/linux_kernel.html": "Linux Kernel",
                "https://www.raspberrypi.com/documentation/computers/camera_software.html": "Camera Software",
                "https://www.raspberrypi.com/documentation/computers/compute-module.html": "Compute Module",
                "https://www.raspberrypi.com/documentation/computers/config_txt.html": "config.txt",
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html": "Raspberry Pi Hardware",
                "https://www.raspberrypi.com/documentation/computers/processors.html": "Processors",
                "https://www.raspberrypi.com/documentation/computers/legacy_config_txt.html": "Legacy config.txt",
                # GPIO
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header": "GPIO and 40-Pin Header",
                # Networking
                "https://www.raspberrypi.com/documentation/computers/remote-access.html#setting-up-an-ssh-server": "SSH Setup",
                "https://www.raspberrypi.com/documentation/computers/remote-access.html#vnc": "VNC Remote Desktop",
                "https://www.raspberrypi.com/documentation/computers/remote-access.html#scp": "SCP File Transfer",
                "https://www.raspberrypi.com/documentation/computers/remote-access.html#rsync": "Rsync File Transfer",
                "https://www.raspberrypi.com/documentation/computers/remote-access.html#nfs": "NFS Network File System",
                "https://www.raspberrypi.com/documentation/computers/remote-access.html#samba": "Samba/CIFS Sharing",
                # Configuration pages
                "https://www.raspberrypi.com/documentation/computers/configuration.html#setting-up-a-headless-raspberry-pi": "Headless Setup",
                "https://www.raspberrypi.com/documentation/computers/configuration.html#wireless-networking": "Wireless Networking",
                "https://www.raspberrypi.com/documentation/computers/configuration.html#using-a-proxy-server": "Proxy Server",
                "https://www.raspberrypi.com/documentation/computers/configuration.html#configuring-networking": "Network Configuration",
                "https://www.raspberrypi.com/documentation/computers/configuration.html#setting-up-a-routed-wireless-access-point": "Wireless AP",
                "https://www.raspberrypi.com/documentation/computers/configuration.html#using-a-usb-webcam": "USB Webcam",
                "https://www.raspberrypi.com/documentation/computers/configuration.html#audio-configuration": "Audio Configuration",
                "https://www.raspberrypi.com/documentation/computers/configuration.html#external-storage": "External Storage",
                "https://www.raspberrypi.com/documentation/computers/configuration.html#localisation": "Localisation",
                "https://www.raspberrypi.com/documentation/computers/configuration.html#users": "Users",
                "https://www.raspberrypi.com/documentation/computers/configuration.html#kernel-command-line": "Kernel Command Line",
                # OS pages
                "https://www.raspberrypi.com/documentation/computers/os.html#using-apt": "Using APT",
                "https://www.raspberrypi.com/documentation/computers/os.html#using-python": "Using Python",
                "https://www.raspberrypi.com/documentation/computers/os.html#playing-audio-and-video": "Playing Audio/Video",
                "https://www.raspberrypi.com/documentation/computers/os.html#utilities": "OS Utilities",
                "https://www.raspberrypi.com/documentation/computers/os.html#updating-and-upgrading": "Updating and Upgrading",
                "https://www.raspberrypi.com/documentation/computers/os.html#gpio-and-the-40-pin-header": "GPIO on the OS",
                # Camera
                "https://www.raspberrypi.com/documentation/computers/camera_software.html#rpicam-apps": "rpicam-apps",
                "https://www.raspberrypi.com/documentation/computers/camera_software.html#rpicam-hello": "rpicam-hello",
                "https://www.raspberrypi.com/documentation/computers/camera_software.html#rpicam-jpeg": "rpicam-jpeg",
                "https://www.raspberrypi.com/documentation/computers/camera_software.html#rpicam-still": "rpicam-still",
                "https://www.raspberrypi.com/documentation/computers/camera_software.html#rpicam-vid": "rpicam-vid",
                "https://www.raspberrypi.com/documentation/computers/camera_software.html#rpicam-raw": "rpicam-raw",
                "https://www.raspberrypi.com/documentation/computers/camera_software.html#rpicam-detect": "rpicam-detect",
                # Raspberry Pi models
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-5": "Raspberry Pi 5",
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-4-model-b": "Raspberry Pi 4 Model B",
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-3-model-b": "Raspberry Pi 3 Model B",
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-zero-2-w": "Raspberry Pi Zero 2 W",
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-zero-w": "Raspberry Pi Zero W",
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-400": "Raspberry Pi 400",
                # Boot
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-boot-eeprom": "Boot EEPROM",
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-bootloader-configuration": "Bootloader Config",
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#usb-mass-storage-boot": "USB Boot",
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#network-booting": "Network Boot",
                "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-boot-mode": "GPIO Boot Mode",
            },
        },
        "microcontrollers": {
            "pages": {
                # Pico / RP2040
                "https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html": "Pico Series Overview",
                "https://www.raspberrypi.com/documentation/microcontrollers/raspberry-pi-pico.html": "Raspberry Pi Pico",
                "https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html#pico-2-technical-specification": "Pico 2 Technical Spec",
                "https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html#pico-w-technical-specification": "Pico W Technical Spec",
                "https://www.raspberrypi.com/documentation/microcontrollers/rp2040.html": "RP2040",
                "https://www.raspberrypi.com/documentation/microcontrollers/rp2350.html": "RP2350",
                # SDK
                "https://www.raspberrypi.com/documentation/microcontrollers/c_sdk.html": "C/C++ SDK",
                "https://www.raspberrypi.com/documentation/microcontrollers/micropython.html": "MicroPython",
                # C SDK details
                "https://www.raspberrypi.com/documentation/microcontrollers/c_sdk.html#quick-start-your-own-project": "C SDK Quick Start",
                "https://www.raspberrypi.com/documentation/microcontrollers/c_sdk.html#your-first-binaries": "C SDK First Binaries",
                "https://www.raspberrypi.com/documentation/microcontrollers/c_sdk.html#flash-programming-with-swd": "C SDK Flash with SWD",
                "https://www.raspberrypi.com/documentation/microcontrollers/c_sdk.html#using-an-ide": "C SDK Using an IDE",
                # MicroPython details
                "https://www.raspberrypi.com/documentation/microcontrollers/micropython.html#what-is-micropython": "What is MicroPython",
                "https://www.raspberrypi.com/documentation/microcontrollers/micropython.html#drag-and-drop-micropython": "Drag & Drop MicroPython",
                "https://www.raspberrypi.com/documentation/microcontrollers/micropython.html#connecting-to-the-internet-with-pico-w": "Pico W Internet",
                # Debug
                "https://www.raspberrypi.com/documentation/microcontrollers/debug-probe.html": "Debug Probe",
            },
        },
        "accessories": {
            "pages": {
                "https://www.raspberrypi.com/documentation/accessories/camera.html": "Camera Module",
                "https://www.raspberrypi.com/documentation/accessories/display.html": "Display",
                "https://www.raspberrypi.com/documentation/accessories/keyboard-and-mouse.html": "Keyboard and Mouse",
                "https://www.raspberrypi.com/documentation/accessories/sense-hat.html": "Sense HAT",
                "https://www.raspberrypi.com/documentation/accessories/tv-hat.html": "TV HAT",
                "https://www.raspberrypi.com/documentation/accessories/build-hat.html": "Build HAT",
                "https://www.raspberrypi.com/documentation/accessories/ai-kit.html": "AI Kit",
                "https://www.raspberrypi.com/documentation/accessories/ai-camera.html": "AI Camera",
                "https://www.raspberrypi.com/documentation/accessories/m2-hat-plus.html": "M.2 HAT+",
                "https://www.raspberrypi.com/documentation/accessories/audio.html": "Audio",
                "https://www.raspberrypi.com/documentation/accessories/cooler.html": "Active Cooler",
                "https://www.raspberrypi.com/documentation/accessories/cases.html": "Cases",
                "https://www.raspberrypi.com/documentation/accessories/sd-cards.html": "SD Cards",
                "https://www.raspberrypi.com/documentation/accessories/poe-hat.html": "PoE HAT",
            },
        },
        "services": {
            "pages": {
                "https://www.raspberrypi.com/documentation/services/connect.html": "Raspberry Pi Connect",
                "https://www.raspberrypi.com/documentation/services/id.html": "Raspberry Pi ID",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"raspberrypi-{source_key}" if source_key else "raspberrypi"
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
            for suffix in [' - Raspberry Pi Documentation',
                           ' | Raspberry Pi', ' - Raspberry Pi']:
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
                        "category": f"raspberrypi-{source_key}",
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
            self.log.info(f"=== Scraping raspberrypi/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    RaspberryPiScraper(base, source_key).run()
