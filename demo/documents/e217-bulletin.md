# Service Bulletin SB-PX400-217

## Intermittent E-217 after firmware 4.8

A small number of PX-400 installations reported intermittent E-217 stops after updating to firmware 4.8. Engineering review found that the update changed diagnostic timing and may expose marginal encoder connections that previously recovered without a stop.

Do not downgrade firmware as the first response. Inspect the encoder connector and harness, run Diagnostic D-17, and capture the controller log. Escalate to engineering when D-17 passes but repeated E-217 stops continue.

## Parts

Encoder assembly EA-400 and shielded harness HN-44 are the standard service parts for this fault family. Replacement must follow diagnostic evidence rather than the error code alone.
