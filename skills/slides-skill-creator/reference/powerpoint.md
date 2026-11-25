# PowerPoint calibration

PowerPoint places text a little higher or lower than the browser, by an amount that depends on
the font's own metrics. The calibration measures it once per Brand pack with font files and
stores three numbers, `pptxLead`, in `brand.json`. Without them a deck still exports to
PowerPoint, with no vertical correction and a warning. A pack on system fonts has nothing to
calibrate. The model is in `<skill>/engine/docs/pptx-export.md`.

It needs Microsoft PowerPoint, the Engine's export dependencies
(`python3 -m pip install playwright python-pptx fonttools brotli`, and Google Chrome) and
`python3 -m pip install pymupdf`. Ask the maintainer whether they have PowerPoint; if not, leave
the pack uncalibrated and say so.

1. **Prepare** the probe deck outside the skill:
   ```sh
   python3 <gen>/tools/gen.py calibrate prepare --skill-dir <skill> --brand <slug> --out <work>/calibration
   ```
   It builds a deck of 56 probe lines (every size from 20 to 112px at four line heights, in
   regular and bold), exports it to `calibration.pptx` with its layout plan, and writes the
   pack's fonts as TTFs to `<work>/calibration/fonts/`.
2. **Export the PDF through PowerPoint.** Give the maintainer this checklist:
   - Install every font in `<work>/calibration/fonts/`, then quit and reopen PowerPoint.
     Without them PowerPoint draws another face and the numbers are wrong.
   - Open `<work>/calibration/calibration.pptx`.
   - Export it as PDF to `<work>/calibration/calibration.pdf`.

   On macOS, after the fonts are installed and with PowerPoint **quit**, `calibrate prepare ...
   --powerpoint` asks PowerPoint to do the export. It works when the request launches PowerPoint;
   a PowerPoint that is already running can refuse to open the file (error -9074) or wait on a
   dialog. Then quit PowerPoint and try once more, or export by hand.
3. **Fit** and store the numbers:
   ```sh
   python3 <gen>/tools/gen.py calibrate fit --skill-dir <skill> --brand <slug> --out <work>/calibration --write
   ```
   It matches every probe to its line in the PDF and prints `pptxLead` with the remaining error in
   stage pixels. `maxBeforePx` is the worst error before the fit (several pixels for an
   uncalibrated pack). A good fit leaves `sdPx` under 1 and `maxPx` under 2. A large `maxPx`, or
   fewer than 50 of the 56 probes matched (`n`), usually means PowerPoint drew another face
   because the fonts were not installed: fix that and export the PDF again.
4. **Verify**, when the maintainer has time for a second export: run `calibrate prepare` into a
   new folder (the probe deck now carries the new numbers), export the PDF, and run
   `calibrate fit` without `--write`. Its `maxBeforePx` should now be about the first fit's
   `maxPx`. Then remove the probe fonts from the machine if the maintainer does not want them
   installed.
