# X-ray Mirror

A browser page that draws a skull, brain, face muscles, eyes and hand bones over your live camera image. The anatomy follows your head as you move, the jaw opens when you open your mouth, and hand bones appear when you hold up a hand.

Everything runs in the browser tab. The camera video is not recorded and is not sent anywhere.

## Use it

Open the site's `https://` address in Chrome, Edge or Safari, press **Start camera**, and allow camera access. The page must be opened in a real browser tab; previews inside other apps cannot use the camera.

The first start downloads the face and hand tracking models (about 12 MB) from Google's MediaPipe model storage, so it needs an internet connection.

To run it on your own computer instead:

    python3 -m http.server 8000

then open `http://localhost:8000/`.

## Controls

- **Layers**: skull, brain, muscles, eyes, face outline, hand bones, and labels.
- **Look**: X-ray or Solid, brightness, and how much of the real image shows through.
- **Fit to my head**: **Auto-fit to my face** measures your face width and eyes-to-chin length (it also runs once on first use); sliders adjust size, width, height, eyes-to-chin length, depth and position. The anatomy is one adult's, so most people need a small adjustment. Settings are remembered in the browser.
- **Save photo**, **Switch camera** (when the device has more than one), and **Full screen** (where the browser supports it).

## Test status

Tested in headless Chrome with a still photo as the camera feed: face tracking, skull alignment, jaw opening, both looks, labels, the photo button, and the desktop and phone layouts. Hand bones were tested with simulated hand positions only.

Not yet tested: a live webcam, real hand tracking, phones and tablets, Safari and Firefox, and graphics-card acceleration for the tracker.

## How it is built

- `index.html` is the whole app: the page, its code, and the anatomy meshes packed inline.
- `vendor/` holds unmodified copies of three.js 0.160.0 and MediaPipe Tasks Vision 0.10.14, so the page does not depend on a CDN. If those files are missing, the page falls back to jsDelivr.
- `src/template.html` is the page source and `src/mesh_data.js` the packed meshes. `python3 src/make.py` joins them into `index.html`.
- `src/build_meshes.py` produced `mesh_data.js` from the BodyParts3D STL files listed in `src/parts_used.txt`. It simplifies each mesh, aligns the head to MediaPipe's canonical face model, and prepares the right hand as separate bones.

## Credits and licenses

- Anatomy models: **BodyParts3D, (c) The Database Center for Life Science (DBCLS)**, licensed under [CC BY-SA 2.1 Japan](https://creativecommons.org/licenses/by-sa/2.1/jp/deed.en). The meshes in this repository were simplified and rescaled from that dataset and are shared under the same license.
- [three.js](https://threejs.org/) is MIT licensed. [MediaPipe](https://github.com/google-ai-edge/mediapipe) is Apache 2.0 licensed.

This is an illustration for learning and fun. It is not a medical image and shows a generic anatomy model, not the person in front of the camera.
