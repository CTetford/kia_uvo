# Kia Connect Canada (kiaconnect.ca) — gaps vs. kia_uvo / hyundai_kia_connect_api

Audit date: 2026-11-21. Vehicle: 2026 EV9 (CA region, genType G3, CCS2).
Compared against `kia_uvo` main and `hyundai_kia_connect_api` main @ `40decf2` (`KiaUvoApiCA.py`).

Method: read-only. Crawled the `/cwp/overview` and `/remote/*` pages and the web bundle
(`main.b8580be0.chunk.js`), plus the per-vehicle `featuresModel` the portal stores in
`sessionStorage`. No remote commands were sent. VIN, PIN, tokens and location are omitted.

## TL;DR

1. **Heated steering wheel level is never sent for CA.** The portal sends
   `steerWheelHeat_step2` (0 off, 1 low, 2 high) and a separate `sideBackWindowHeat` (0/1)
   when the vehicle has the `2stepSteerWheelHeat` feature (`StrgWhlHeatingOption = 2`).
   `KiaUvoApiCA.start_climate` sends only `heating1`, so the `steering_wheel` service field
   is silently ignored in Canada. Fix proposal below.
2. **CA status parsing misses `steerWheelHeat_step2`**, so the existing
   `steering_wheel_heat_step` sensor is always unknown for CA.
3. Several portal features have no CA support: departure/climate schedules, climate
   favourites, off-peak settings, valet mode, next-service date, preferred dealer,
   notification history, digital key status and subscription expiry.

## 1. Climate command — steering wheel level (high priority)

Portal defaults (from the bundle):

```js
{ airCtrl: 0, defrost: false,
  airTemp: { value: "0BH", unit: 0, hvacTempType: N },
  heating1: 0, sideBackWindowHeat: 0, steerWheelHeat_step2: 0,
  igniOnDuration: 3,
  seatHeaterVentCMD: { drvSeatOptCmd: 0, astSeatOptCmd: 0, rlSeatOptCmd: 0, rrSeatOptCmd: 0 },
  ims: 0 }
```

UI logic:

- Steering button cycles `steerWheelHeat_step2` 0 → 1 → 2 → 0 (`btn_steerwheel_heat_off|low|on`).
  The summary shows "HEATED STEERING WHEEL HI" for 2, "LO" for 1.
- With `has2StepSteerWheelHeat`, the side/back defroster is its own checkbox:
  `sideBackWindowHeat: checked ? 1 : 0`.
- Without it, the older combined `heating1` encoding is used (0 off, 1 unified, 2 side/back, 3 wheel, 4 both).
- Feature flags: `RemoteServices.Climate.StrgWhlHeatingOption = "2"` and `Extended` contains `"2stepSteerWheelHeat"`.

Feature model reported for this EV9:

```json
"Climate": { "Defrost": "1", "SteerwheelHeat": "1", "SideMirrorHeat": "1", "RearWindowHeat": "1",
             "EvSocControl": "1", "Favorite": "1", "PinRequired": "1", "ClimateSetting": "1",
             "TemperatureType": "1", "StrgWhlHeatingOption": "2" },
"Extended": ["2stepSteerWheelHeat", "digitalKey"]
```

Proposed change in `KiaUvoApiCA.start_climate` (both `remoteControl`/`hvacInfo` and ICE `setting` bodies):

```python
body = {...existing keys...}
if options.steering_wheel is not None:
    # CA 2-step wheels: 0 off, 1 low, 2 high (kiaconnect.ca steerWheelHeat_step2)
    body["steerWheelHeat_step2"] = int(options.steering_wheel)
    # 2-step cars control side/back defrost separately from heating1
    body["sideBackWindowHeat"] = 1 if options.heating in (1, 2, 4) else 0
```

Still to verify: the portal's remote start page only saves favourites ("download the app for
remote service"), so the live command field name should be confirmed against an app capture
or one test start before merging. The favourite/schedule bodies use the same keys.

Seat command encoding used by the portal (`M()`): `0 → 0`, `7 → 15`, otherwise
`2 + options[step]` plus `3` when heat (not vent) is selected. This matches the
6/7/8 = low/med/high heat values the integration already sends.

## 2. Status data points not parsed for CA

| Portal field (`lstvhclsts` → `status.*`) | Shown on portal | CA library | Integration entity |
|---|---|---|---|
| `steerWheelHeat_step2` (0/1/2 = OFF/LO/HI) | Heated steering wheel | not parsed | `steering_wheel_heat_step` exists (other regions) |
| `smartKeyBatteryWarning` | Alerts → Smart key battery | not parsed | `smart_key_battery_warning_is_on` exists |
| `engineOilStatus` | Alerts (ICE) | not parsed | `engine_oil_warning_is_on` exists |
| `evStatus.v2L`, `evStatus.v2G` | EV status | not parsed | none |
| `tirePressureFL/FR/RL/RR` (values) | Tire pressure | lamps only | pressure sensors exist for other regions |
| `seatHeaterVentInfo` | Seat state | parsed | ok |
| `evStatus.batteryPreconditiong` | Battery pre-conditioning | parsed | ok |
| `windowOpen.*`, `sunroofOpen`, `lampWireStatus.*` | Windows, lamps | parsed | ok |

## 3. Portal features with no CA implementation

| Feature | Endpoint(s) | Library CA | Notes |
|---|---|---|---|
| Departure / scheduled climate | `GET v2/rc/ev/getresdetails` (`reservedHVACInfo1/2`, `reservHVACSet`), `POST v2/rc/ev/reshvacset` | `schedule_charging_and_climate` raises "Departure/climate schedules are not supported" | Same body shape as climate (`airCtrl`, `airTemp`, `defrost`, `heating1`, `sideBackWindowHeat`, `steerWheelHeat_step2`) |
| Off-peak settings (G3 EV) | `evc/gopter`, `evc/sopter` | not used | `offpeakPowerInfo.offPeakPowerTime1/2`, `offPeakPowerFlag`; integration has `set_off_peak_charging` for other regions |
| Legacy charge schedule | `evc/grcfs`, `evc/srcfs`, `evc/glcfs` | not used | `reservChargeInfos`, `offpeakPowerInfo` |
| Climate favourites | `gtfvsttng`, `svfvsttng`, `rmfvsttng`, `svdefaultfvsttng` | none | Up to 3 presets with a default |
| Valet mode | `valet/activate`, `valet/deactivate`, `valet/lastvaletstatus` | `supports.valet_mode = False` | Menu lists `ValetParkingMode`; services already exist for other regions |
| Next service date / interval | `nxtsvc`, `gtsvcodm`, `svsvcodm`, `svcodmt` (reset) | distance only | Portal shows last/next service date, days left, interval months/km, "maintenance due" |
| Preferred dealer | `gtprfrdlr` | none | Name, address, phone, hours |
| Notification history | `v2/ntfhst`, `ntcmsgcnt`, `ntcmsglst` | none | Could feed an event entity |
| Digital key | `dkc/dkeystatus`, `dkc/compatibility` | none | Status sensor only; enrol/terminate should stay out |
| Subscription | `billing/retrieve/account/overview` | none | Expiry / plan as a diagnostic sensor |
| Monthly vehicle report | `gtmvrlst`, `gtmvrrpt`, `gtmvrdy`, `svmvrdy` | list/report parsed | Report day setting not exposed |
| Vehicle nickname | `chngvhclncknm` | none | Low value |
| Hazard lights / horn | Feature flags `HornLights`, `FlashLights` | none | Not in the web bundle (app only). Needs an app capture. |

## 4. Remote tab map (portal)

Tabs: `charge` (start/stop charge: `evc/rcstrt`, `evc/rcstp`), `start` (engine start settings),
`schedule`, `climate` (climate settings and favourites), `tsoc` (target SoC: `evc/selsoc`,
`evc/setsoc`, `v2/ev/reserv/socset` for multi-plug). Lock, unlock, horn/lights and climate start
are app-only on the web ("DOWNLOAD_APP_FOR_REMOTE_SERVICE").

## 5. Full endpoint list from the web bundle

Account and auth: `v2/login`, `mfa/selverifmeth`, `mfa/sendotp`, `mfa/validateotp`, `mfa/genmfatkn`,
`mfa/validateCaptcha`, `mfa/verifyMfaPsswd`, `otp/checkemail`, `otp/sendemailotp`, `otp/validateemailotp`,
`vrfyacctkn`, `acctinfo`, `svacctgl`, `svacctprf`, `chngpsswd`, `chngpin`, `vrfypin`, `lgout`, `v4/account`.

Vehicles: `vhcllst`, `v2/myvehicle`, `sltvhcl`, `addvhcl`, `lstvhclsts`, `rltmvhclsts`, `rmtsts`,
`other/rmtsts`, `chngvhclncknm`, `v2/account/vehicle`, `v4/vehicle/validate`, `v4/rmuservin`,
`vin/photo`, `vin/photo/delete`, `vin/dismisswarn`.

EV and climate: `evc/rcstrt`, `evc/rcstp`, `evc/selsoc`, `evc/setsoc`, `evc/gopter`, `evc/sopter`,
`evc/grcfs`, `evc/srcfs`, `evc/glcfs`, `v2/ev/reserv/socset`, `v2/rc/ev/getresdetails`,
`v2/rc/ev/reshvacset`, `v2/rc/ev/reschargeset`, `gtfvsttng`, `svfvsttng`, `rmfvsttng`, `svdefaultfvsttng`.

Service: `nxtsvc`, `gtsvcodm`, `svsvcodm`, `svcodmt`, `gtmvrlst`, `gtmvrrpt`, `gtmvrdy`, `svmvrdy`,
`gtprfrdlr`, `svprfrdlr`, `gtnrbydlr`.

Notifications: `gtntfsttng`, `ntfsttng`, `gtntfsttngtyps`, `ntfhst`, `v2/ntfhst`, `ntcmsgcnt`,
`ntcmsglst`, `ntcmsgmd`, `ntcmsdmg`, `ntcmsgumst`, `urlcnt`.

Other: `valet/*`, `dkc/*`, `calendar/account/*`, `billing/*`, `usrpro*`, `unlinkPfl/*`,
`inviteseconduser`, `getprofilelog`, `tmuprofSynRes`, `prov/suspend/undo`.

Request headers (portal): `from: CWP`, `offset`, `language`, `accessToken`, `vehicleId`, `pAuth`
(PIN token). `setsoc` overrides `from: SPA`.

## Suggested order

1. Send `steerWheelHeat_step2` + `sideBackWindowHeat` in CA `start_climate` (small, high value).
2. Parse `steerWheelHeat_step2` and `smartKeyBatteryWarning` in CA status.
3. Departure climate schedules via `reshvacset`.
4. Valet mode, next-service date, subscription expiry.
