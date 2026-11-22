# Canada (kiaconnect.ca) parity branch

Branch `feature/ca-kiaconnect-parity` in this fork and in
[CTetford/hyundai_kia_connect_api](https://github.com/CTetford/hyundai_kia_connect_api/tree/feature/ca-kiaconnect-parity).
Adds the kiaconnect.ca web app features the Canadian API was missing.
Request bodies come from the portal's code; response shapes come from live
captures on a 2026 EV9 (G3), 2026-11-21.

The library branch also carries `fix/ca-heated-wheel-and-seats`
(steering wheel level and seat-status fixes).

## What's new

| Feature | Endpoint(s) | In Home Assistant | Verified |
|---|---|---|---|
| Steering wheel level | `steerWheelHeat_step2`, `sideBackWindowHeat` in climate start | `steering_wheel` field of `start_climate` | Live: High and Low reported back |
| Seat / wheel status | `seatHeaterVentInfo`, `steerWheelHeat_step2` | seat sensors, `steering_wheel_heat_step` | Live |
| Departure climate schedules | read: `lstvhclsts` `reservChargeInfos`; write: `v2/rc/ev/reshvacset` | existing departure switches/time sensors, `schedule_charging_and_climate` | Read: live. Write: body matches portal exactly; the EV9 fails it (see below) |
| Valet mode | `valet/activate`, `valet/deactivate`, `valet/lastvaletstatus` | existing valet switch and buttons | Status read: live. Commands: body inferred (portal registers but never calls them) |
| Next/last service date, interval | `nxtsvc` | `next_service_date`, `last_service_date` sensors | Live |
| Reset service reminder | `svcodmt` | `kia_uvo.set_last_service` | Body from portal |
| Vehicle nickname | `chngvhclncknm` | `kia_uvo.set_vehicle_nickname` | Body from portal |
| Climate presets | `gtfvsttng`, `svfvsttng`, `rmfvsttng`, `svdefaultfvsttng` | `save/delete/set_default_climate_favourite`; list in the vehicle data sensor | List: live. Writes: body from portal |
| Monthly report day | `gtmvrdy`, `svmvrdy` | `monthly_report_day` sensor, `kia_uvo.set_monthly_report_day` | Read: live |
| Preferred dealer | `gtprfrdlr` (POST) | `preferred_dealer_name` sensor (+ code, address, phone, website) | Live |
| Notices / notification history | `ntcmsgcnt`, `v2/ntfhst` | `unread_message_count` sensor (+ last 10 notifications) | Live |
| Digital key | `dkc/dkeystatus` (GET) | `digital_key_activated` binary sensor | Live |
| Kia Connect plan | `billing/retrieve/account/overview` (GET), `vhcllst` | `connect_plan_type`, `connect_subscription_end_date` sensors | Live |
| Charge limits (CCS2) | `v2/ev/reserv/socset` (`targetSOClist`) for Gen3 cars, `evc/setsoc` otherwise | existing charge-limit numbers | Live: socset completes; setsoc rejected (7999) on the EV9 |
| Status extras | `smartKeyBatteryWarning`, `engineOilStatus`, `batterySoh`, `dischargingLimit` | existing sensors now populated | Live |

Account data (valet status, dealer, notices, digital key, plan, presets,
report day) refreshes at most every 6 hours, and after any account service.
Each call is independent, so one failure doesn't block the others or the
vehicle update.

## Not implemented

- `evc/gopter`, `evc/sopter`: registered in the portal but never called;
  `gopter` returns only the vehicle id.
- Lock, horn/lights, windows, frunk, charge port, navigation, camera: app-only,
  not in the web app.
- `alerts/maintenance/evTripDetails` (existing trip call) fails for this EV9;
  it isn't a portal endpoint.

## Known limits

- Schedule writes fail on the 2026 EV9 (CCS2, G3). A capture of
  kiaconnect.ca's own Departure **Submit** (2026-11-21) sent the same body the
  library sends and failed the same way: request accepted, then the vehicle
  transaction fails within a second (`RMT-E0209` departures, `RMT-E0208`
  charge window, status `7999`), even for an unchanged schedule and for a
  slot-1-only body. No CCS2 variant exists under `v2/ev/reserv/` (404). The
  Kia app likely uses a different API for CCS2 schedules. HA reports the
  failed action.

- Canada rejects a remote climate start with climate off (`airCtrl: 0`,
  action status 6514). Seats and the wheel only run with climate on.
- Valet status mapping: this EV9 reported `valetMode: 1` while not in valet
  mode, so 1 = inactive, 0 = active. The EU enum differs.
- `manifest.json` points at the library branch by git URL. Home Assistant
  doesn't reinstall a URL requirement when the package is already installed,
  so an existing install needs the library replaced manually.
