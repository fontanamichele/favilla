# Capturing a protocol from SteelSeries GG

Features like the Apex Pro actuation point or key remapping are configured by
SteelSeries GG on Windows. To support them on Linux we need to see the USB
packets GG sends. This guide records them with Wireshark.

Observing how a program works to make other software interoperate with it is
generally allowed in the EU (Directive 2009/24/EC, articles 5 and 6). Do not
share GG's own files or firmware; the packets you capture are fine to share.

## Before you start

- **Privacy:** a capture records everything the device sends, including every
  key you press. Do not type passwords or private text while capturing, and
  read the capture before sharing it.
- Use the same connection you want to support: dongle, cable, or both in
  separate captures.
- Never capture or replay firmware updates.

## Setup (Windows)

1. Install [Wireshark](https://www.wireshark.org/) and tick **USBPcap** in the
   installer. Reboot when asked.
2. Plug in the device and open SteelSeries GG.
3. Open Wireshark. Each `USBPcapN` entry is a USB controller: start a capture
   on one, move the mouse or press a key, and see if packets appear. Keep the
   one where they do.

## Capturing

Change **one setting at a time** and write down when you did it:

1. Start the capture.
2. Wait 5 seconds without touching anything.
3. Change one setting in GG, for example the actuation point of the `A` key
   from 1.5 mm to 2.0 mm.
4. Wait 5 seconds.
5. Change the same setting to a third value (2.0 mm → 3.0 mm). Two changes
   make it easy to tell which bytes hold the value.
6. Stop and save as `.pcapng`, with a name that says what you did:
   `apex-actuation-A-1.5-2.0-3.0.pcapng`.

Useful first captures for the Apex Pro Mini:

- actuation point of one key, then of all keys;
- Rapid Trigger on and off, and its sensitivity;
- remapping one key, and a key on the Fn layer;
- switching onboard profile;
- GG showing the battery level.

## Reading a capture

1. Find the device address: filter on `usb.idVendor == 0x1038`, open one of
   the descriptor packets and note `usb.device_address` (also shown in the
   Source/Destination columns, like `1.5.0`).
2. Keep only the control transfers of that device, where feature reports
   travel (replace 5 with your address):

   ```
   usb.device_address == 5 && usb.transfer_type == 0x02
   ```

Feature reports appear as `SET_REPORT` requests with a payload; output
reports as `URB_INTERRUPT out` or `SET_REPORT` of type output. On Linux,
`tshark` can export them for analysis:

```bash
tshark -r capture.pcapng -Y "usb.device_address == 5 && usbhid.setup.bRequest == 0x09" \
  -T fields -e frame.time_relative -e usb.data_fragment
```

## Sharing

Open an issue with the captures and the notes about what you changed and when.
