# Heat Guardian

A wristband that watches an older person's body heat during hot weather and warns her, and her family, **before** she gets into danger.

Heat waves kill older people quietly: they often do not feel thirsty or hot until it is late. Heat Guardian estimates her core body temperature from the wrist every minute, forecasts the next 20 minutes, and walks her through simple actions (drink, cool down, lie down) with a vibration and a short message on the screen. If she does not respond, her phone texts the family.

Built for the WAICY competition. Not a medical device (see [Honesty](#honesty)).

## What is in this repository

| Folder | What |
|---|---|
| `firmware/` | The band's firmware. `09_guardian/` is the product firmware; `08_logger/` and `poc_*` are the earlier steps; `tools/` has the host tests (the firmware logic compiled and tested on a PC); `bench-tests/` has the flashing script |
| `model/` | Everything that learns, simulates and plans (Python + C): `sim/` Virtual Elders, `model/` the core-temperature network (hg2), `guardian/` the alert rules, `twin/` the personal Body Twin, `tomorrow/` the Tomorrow Engine, `tests/` the test reports and test code |
| `app/` | The iPhone app (SwiftUI, Xcode project) |
| `demo/` | The demo web page ("simulation monitor") used in the WAICY film |
| `case/` | The 3D-printed case: CAD scripts (Python) and printable STL files |
| `release/` | The demo firmware ready to flash (`.uf2` and `.zip`), with md5 / sha256 and `BUILD_INFO.txt` |
| `docs/` | Architecture, decisions log, delivery and review reports, research notes |

## The hardware

- **Seeed XIAO nRF52840 Sense**: the microcontroller (Bluetooth LE, on-board flash for the minute log)
- **1.69 inch ST7789 colour screen** (Waveshare): status gauge and short Greek messages
- **2 x TMP117**: precise skin temperature (inside, insulated) and a reference temperature
- **SHTC3**: air temperature and humidity
- **MAX30102**: heart rate (optical, PPG)
- **ICM-20649**: motion (activity, falls / impacts, wrist raise to wake the screen)
- **DRV2605L** haptic driver + vibration motor
- One push button, a LiPo battery

The wiring of the prototype is in `firmware/09_guardian/README.md` (section "Wiring on board B").

## How the model works

1. **Virtual Elders (sim-to-real).** There is no large public dataset of older people's core temperature during heat waves. So we built a simulated population of 500 older adults (`model/sim/velders/`): a physiological body model with different ages, body sizes, fitness, medicines (for example beta-blockers and diuretics) and homes, living through ordinary days and heat waves, with simulated wrist sensors. Its validation against published heat studies is in `model/sim/VALIDATION.md` (it passes some checks and fails others; the failures are listed with the reason).
2. **Core temperature from the wrist.** A small neural network (Core Sense hg2, an ensemble of 5 networks, about 27 KB) fuses skin temperature, a heat-flux term, a heart-rate-based estimate, air temperature and humidity. It gives the current core temperature **with a range**, and a **forecast 20 and 30 minutes ahead**. It runs on the band itself, once a minute. The same C code is tested bit for bit against the Python version.
3. **Body Twin.** The band slowly learns a few personal constants for its wearer (`model/twin/`).
4. **The alert ladder.** Rules on top of the forecast decide what to do (`model/guardian/`, `firmware/09_guardian/hg_fw_alert.c`, `hg_fw_ladder.c`):
   reminder by cause (drink / cool down) -> she presses the button = done -> 20 minutes later the band checks whether the forecast stopped rising -> if not, it escalates («Πηγαίνετε κάπου δροσερά», «Ξαπλώστε, βρέξτε τον λαιμό σας») -> if she does not answer the question «Είστε καλά;», the family is alerted. The band only buzzes when the readings are trustworthy (worn, plausible skin temperature, no shower or direct sun on the sensor) and the warning has lasted a few minutes, to avoid false alarms.
5. **Tomorrow Engine.** Takes tomorrow's real weather forecast (Open-Meteo), models how hot her home gets, and runs her simulated body through the day to find the risky hours and the best time to go out (`model/tomorrow/`).

## The iPhone app

The app (`app/`) runs on her phone (SwiftUI, iOS 26, no third-party packages). It does three jobs: a simple **setup** (pair the band, her age and medicines, 1 to 3 family contacts), **the Tower** (keeps the Bluetooth link in the background, sends tomorrow's plan to the band, and turns band alerts into SMS to the family, through Twilio or an iPhone Shortcut), and **history + a PDF report** for the doctor. Details: `app/README.md`. To build it, open `app/HeatGuardian.xcodeproj` in Xcode and choose your own signing team.

## The demo: "hardware in the loop"

In the demo, the **real band runs its real firmware**, but the person is **simulated**: the firmware replays one Virtual Elder (a simulated woman in her mid-seventies) through a heat episode, minute by minute, through the same estimator, forecast and alert ladder that run in normal use. **The band's sensors are not used during the replay.** The demo page draws only what the band reports over Bluetooth (or USB): her simulated true core temperature, the band's estimate, its 20-minute forecast, the gauge colour and each ladder step. You press the band's real button when it asks, or tick "She doesn't respond" to see the family alert path.

### Flash the demo firmware

The flash file is **`release/09_guardian_v0917_demo_b7g.zip`** (firmware `09-guardian-0.9.17-demo-b7g`; the same build as `.uf2` beside it). `BUILD_INFO.txt` lists the exact build and its checksums.

- **Easiest (macOS, needs `adafruit-nrfutil`):**

      bash firmware/bench-tests/flash_band.command release/09_guardian_v0917_demo_b7g.zip

- **By hand (any computer):** plug the band in by USB, double-press the XIAO's reset button, a drive called `XIAO-SENSE` appears, copy the `.uf2` file onto it. The band restarts by itself.

Check the checksum first if you like: `shasum -a 256 release/*.uf2` and compare with the `.sha256` file.

### Run the demo page

The page needs Chrome (Web Bluetooth / Web Serial) and a local web server:

    cd demo
    python3 -m http.server 8765

Open `http://localhost:8765`, click **Connect band**, then **Simulate heat episode**. Without a band, **Preview without band** plays a recording of the same replay made by the host build of the firmware.

The **evidence corner** (bottom right of the page) shows that the band is really live: the link and the seconds since the band's last message, the firmware string the band itself reports, the firmware commit (shown only when the band reports this build, `b7g`), the hash of the frozen model, the simulated person's id, the wall clock, and a QR code to this repository.

The **Tomorrow** view first shows how the plan is made: 7 simulated days of wear for the same Virtual Elder, the Body Twin learning her body from them (the real twin code), then the Tomorrow Engine on tomorrow's real forecast for a hot city. It needs a plan: `./make_tomorrow.command` (it downloads that forecast). Full instructions: `demo/README.txt`.

### Run the tests (optional)

- Firmware logic on a PC: `bash firmware/tools/run_host_tests.sh` (gcc)
- Demo page parser: `node demo/tools/test_parser.js`
- Python parts: `pytest` inside `model/sim`, `model/twin`, `model/tomorrow`

Some large test fixtures (golden traces over 512 KB) are not in this snapshot to keep it small, so a few tests that need them will skip or fail.

## Honesty

- **The demo episodes are simulated people (Virtual Elders), not real patients.** No older person's data is in this repository.
- **The person in the demo was picked as a showcase.** Out of a few hundred simulated women run through the same heat scenario, we chose one of those the band tracks most accurately that still shows every step of the ladder. A typical person's error is larger; the numbers below are the fair ones.
- **The accuracy numbers are on simulated data.** On the simulated calibration group, the core estimate is off by about 0.15 °C on average now and 0.16 °C for the 20-minute forecast (`model/model/REPORT_MODEL.md`). On the only real data we had (young adults walking in a heat chamber), it was off by about 0.28 °C and was **not better** than a simple heart-rate baseline. A simulation that is wrong in a systematic way would make these numbers look better than reality.
- **It has not been tested on older people wearing it.** The firmware has run on our prototype band; long wear, battery life and real heat waves are not yet tested.
- The held-out test sets (the "sealed exam") are kept private so they stay unseen; they are not in this repository.
- **Heat Guardian is not a medical device.** It is a student research prototype. It is not certified, it does not diagnose anything, and it must not replace medical care or calling emergency services.

## Credits

- Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).
- The demo page's QR encoder (`demo/tools/qr.js`) is Kazuhiko Arase's QRCode for JavaScript (MIT), as vendored in qrcode-terminal (Apache-2.0).
- Physiology sources are cited in `docs/research/` and `model/sim/VALIDATION.md`.

## License

MIT, see `LICENSE`. Third-party pieces keep their own licenses (noted in the files).
