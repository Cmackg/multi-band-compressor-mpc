# Installing Multi-Band Compressor

## Requirements
- An MPC running **MPC OS 3.10.1 or later**: MPC Live III, XL and other 64-bit MPCs, or MPC X, Live, Live II, One, One+,
  Key 61, Key 37 and Force (32-bit). This one folder works on all of them.
- **External Plugin Support switched on**: Preferences → Enhancements → turn on **Enable Enhancements** and
  **External Plugin Support**.

## Install
1. Unzip. You get one folder named **`Cmackg - VST - Multi-Band Compressor`** (this file is inside it).
2. On a USB drive, an SD card or the MPC's internal drive, make a folder named **`VST2 Plugins`** at the top level, if
   there isn't one already.
3. Copy the `Cmackg - VST - Multi-Band Compressor` folder itself into `VST2 Plugins`. Don't rename it, don't move
   anything out of it, and don't put it inside another folder: `plugin.json` must end up at
   `VST2 Plugins/Cmackg - VST - Multi-Band Compressor/plugin.json`. If your computer unzipped it into an extra folder
   (named after the zip), open that and copy the `Cmackg - VST - ...` folder from inside it.
4. Put the drive in the MPC (or restart the MPC if you used the internal drive). Add it to a track as an insert
   effect: it's listed under **External VST Plugins** as **Multi-Band Compressor**.

## Remove
Delete the folder from `VST2 Plugins`.

## If something goes wrong
Third-party plugins run inside the MPC software. If the MPC misbehaves after adding it, remove the folder from the
drive and restart. Please report the problem with your MPC model and OS version.
