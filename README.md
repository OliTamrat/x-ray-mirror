# X-ray Mirror

A browser page that draws anatomy over a live camera image, for teaching.

- **Head and hands**: skull, brain, face muscles, eyes and hand bones follow the face in close-up. The jaw opens with the mouth.
- **Full body**: a complete skeleton and the main organs (heart, lungs, liver, stomach, spleen, kidneys, bladder, intestines, airways) follow the shoulders, arms, hips and legs.

Everything runs in the browser tab. The camera video is not recorded and is not sent anywhere.

The anatomy is one reference adult's, placed using points tracked on the surface of the body. It shows where structures are and what they look like. It does not show the inside of the person in view and must not be used for diagnosis.

## Use it

Open the site's `https://` address in Chrome, Edge or Safari, press **Start camera**, and allow camera access. The page must be opened in a real browser tab; previews inside other apps cannot use the camera.

The first start downloads the face and hand tracking models (about 12 MB) from Google's MediaPipe model storage, so it needs an internet connection.

To run it on your own computer instead:

    python3 -m http.server 8000

then open `http://localhost:8000/`.

## Controls

- **View**: Head and hands, or Full body. Full body downloads a body-tracking model (about 9 MB) the first time.
- **Layers**: bones, organs, brain, face muscles, eyes, face outline, hand bones, and labels.
- **Look**: X-ray or Solid, brightness, and how much of the real image shows through.
- **Fit to my head**: **Auto-fit to my face** makes small adjustments to width and jaw length (it also runs once on first use); sliders adjust size, width, height, jaw length, depth and position. The anatomy is one adult's, so most people need a small adjustment. Settings are remembered in the browser.
- **Save photo**, **Switch camera** (when the device has more than one), and **Full screen** (where the browser supports it).

## Test status

Tested in headless Chrome with a still photo as the camera feed:

- Head view: face tracking, skull alignment, jaw opening, lips following the jaw, both looks, labels, auto-fit, the photo button, desktop and phone layouts.
- Full-body view: the skeleton and organs were posed from simulated joint positions (standing, arm raised, elbow and knee bent). Real body tracking was run on a head-and-shoulders photo only, where the skull, neck, ribs and chest organs landed on the right places.
- Switching between the two views and back.

Not yet tested: a live camera in full-body view, a real full-length person, phones and tablets in full-body view, Safari and Firefox in full-body view, hand bones on a real hand, and graphics-card acceleration for the tracker.

Known limits of the full-body view: body tracking gives 33 points for the whole body, so the fit is looser than the head. The torso is posed as one piece, fingers and toes do not bend, and forearm rotation is not followed.

## How it is built

- `index.html` is the whole app: the page, its code, and the anatomy meshes packed inline.
- `vendor/` holds unmodified copies of three.js 0.160.0 and MediaPipe Tasks Vision 0.10.14, so the page does not depend on a CDN. If those files are missing, the page falls back to jsDelivr.
- `src/template.html` is the page source and `src/mesh_data.js` the packed head and hand meshes. `python3 src/make.py` joins the template and data into `index.html`.
- `src/body_data.js` holds the packed body skeleton and organs, produced by `src/build_body.py` from the parts listed in `src/body_parts_used.txt`.
- `src/build_meshes.py` produced `mesh_data.js` from the BodyParts3D STL files listed in `src/parts_used.txt`. It simplifies each mesh, aligns the head to MediaPipe's canonical face model, and prepares the right hand as separate bones.

## Credits and licenses

- Anatomy models: **BodyParts3D, (c) The Database Center for Life Science (DBCLS)**, licensed under [CC BY-SA 2.1 Japan](https://creativecommons.org/licenses/by-sa/2.1/jp/deed.en). The meshes in this repository were simplified and rescaled from that dataset and are shared under the same license.
- [three.js](https://threejs.org/) is MIT licensed. [MediaPipe](https://github.com/google-ai-edge/mediapipe) is Apache 2.0 licensed.

This is an illustration for learning and fun. It is not a medical image and shows a generic anatomy model, not the person in front of the camera.
