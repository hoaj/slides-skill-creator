# Third-party licences

`engine/runtime/pptxgen.bundle.js` is the published `dist/pptxgen.bundle.js` of PptxGenJS
3.12.0. It carries the libraries below. The files here are their licence texts, copied
unchanged from each project's official npm package, with two exceptions: `pako-zlib.txt`
is the notice at the top of pako's zlib source files, without the comment markers, and
`set-immediate-shim.txt` comes from the project's repository at tag v1.0.1, because its
npm package has no licence file.

| Library | Version in the bundle | Licence | Text |
|---|---|---|---|
| PptxGenJS | 3.12.0 | MIT | [PptxGenJS.txt](PptxGenJS.txt) |
| JSZip | 3.5.0 | **MIT** (dual-licensed MIT or GPLv3; this project uses it under MIT) | [JSZip.markdown](JSZip.markdown) |
| pako | 1.0.5 | MIT, with zlib-licensed parts | [pako.txt](pako.txt), [pako-zlib.txt](pako-zlib.txt) |
| lie | 3.3.0 | MIT | [lie.md](lie.md) |
| immediate | 3.0.6 | MIT | [immediate.txt](immediate.txt) |
| set-immediate-shim | 1.0.1 | MIT | [set-immediate-shim.txt](set-immediate-shim.txt) |
| @babel/polyfill | 7.x | MIT | [babel-polyfill.txt](babel-polyfill.txt) |
| core-js | 2.6.11 | MIT | [core-js.txt](core-js.txt) |
| regenerator-runtime | 0.13.x | MIT | [regenerator-runtime.txt](regenerator-runtime.txt) |
| tslib helpers | 2.x | 0BSD | [tslib.txt](tslib.txt) |

The bundle states the versions of PptxGenJS, JSZip and core-js. The pako, lie, immediate and
set-immediate-shim versions are the ones whose sources appear unchanged in the published
JSZip 3.5.0 build. The bundle does not record the exact @babel/polyfill,
regenerator-runtime or tslib versions, so the table gives the major line.

**One change to the bundle.** One character inside a base64 image string is written as the
equivalent JavaScript escape `\x74`, so a text scan of this public repo does not match a
chance letter sequence. The string's value and the code's behaviour are unchanged.
