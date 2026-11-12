# X-ray Mirror

A browser page that draws anatomy over a live camera image, for teaching.

- **Head and hands**: skull, brain, face muscles, eyes and hand bones follow the face in close-up. The jaw opens with the mouth.
- **Full body**: a complete skeleton and the main organs (heart, lungs, liver, stomach, spleen, kidneys, bladder, intestines, airways) follow the shoulders, arms, hips and legs.

Everything runs in the browser tab. The camera video is not recorded and is not sent anywhere.

The anatomy is one reference adult's, placed using points tracked on the surface of the body. It shows where structures are and what they look like. It does not show the inside of the person in view and must not be used for diagnosis.

## Design

- **Landing view**: before the camera starts, the page shows the reference model turning slowly, with a short introduction and two actions: Start camera, or Explore the model. The model view needs no camera: drag to turn it, tap parts, zoom into regions and run the quiz.
- **Themes**: Auto (follows the device), Dark and Light, switched from the header. The picture itself always stays dark, like a film on a light-box.
- **Type**: Bricolage Grotesque for the wordmark and headings, IBM Plex Sans for text, IBM Plex Mono for labels and readouts. The fonts are open-licensed (SIL OFL) and hosted with the app in `vendor/fonts`, so they work offline. They cover Latin script; another script such as Ethiopic would need an added font.
- **Side marker**: an "L" in the corner of the picture marks the subject's left, as on a radiograph.
- On a small screen a full-body view has too many labels to read, so it shows dots; names appear on tap or after zooming into a region.

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

## Learning features

- **Tap to learn**: tap a label or a dot on the picture to read what that part is, what it does and one thing worth knowing. There are 54 entries covering the head, skeleton and organs.
- **Focus and zoom**: buttons under the picture zoom into the head, chest, abdomen, an arm or the legs and follow that region as the person moves. The + and - buttons zoom further. Labels and the quiz then cover only what is in view.
- **Quiz me**: labels are hidden and the page asks you to tap a named part, then keeps score. In the full-body view a tap anywhere on the organ or bone counts, because taps are tested against the real shapes. **Show me** reveals the answer.
- **Language**: English or Afaan Oromo. The Afaan Oromo names and one-line descriptions are a **draft translation** and need review by a fluent health educator before classroom use. All teaching text lives in one block, `INFO`, near the top of the script in `src/template.html`, one line per structure, so corrections are simple edits.

## Learner progress

- Type a name in the **Learner** box under the picture. Each learner's quiz results are kept separately.
- For every structure the page records how many questions were asked, how many were right on the first tap, wrong taps, and how often the answer had to be shown.
- The table lists the parts that need most practice, and the quiz asks weak and unseen parts more often.
- **Export results (CSV)** saves all learners' results as a spreadsheet file.
- Results are stored only in the browser on that device (localStorage). Nothing is sent to a server, so results do not follow a learner to another device, and clearing the browser's site data erases them.

## Offline use

- Press **Save for offline use** once while connected. It stores the page, the 3D and tracking libraries and the three tracking models (about 30 MB) on the device.
- After that the app opens and runs with no internet, from the same address or from a home-screen icon ("Add to Home Screen" in the browser's share menu).
- When a connection is available the page itself is fetched fresh, so updates still arrive. Files under `vendor/` are served from the saved copy; `sw.js` holds a cache version to bump when they change.

## Test status

Tested in headless Chrome with a still photo as the camera feed:

- Head view: face tracking, skull alignment, jaw opening, lips following the jaw, both looks, labels, auto-fit, the photo button, desktop and phone layouts.
- Full-body view: the skeleton and organs were posed from simulated joint positions (standing, arm raised, elbow and knee bent). Real body tracking was run on a head-and-shoulders photo only, where the skull, neck, ribs and chest organs landed on the right places.
- Switching between the two views and back.
- Focus and zoom on each region, and quiz rounds of ten questions in the whole view and in the chest and abdomen views with off-centre taps (simulated pose, mouse taps).
- The redesigned page at desktop and phone sizes in both themes: landing view, model view (tap, zoom, language switch), and the change to the live camera view.
- Learner progress: a quiz with a first-tap answer, a wrong-then-right answer, a shown answer and a double tap; the summary, table, CSV export, and results surviving a reload.
- Offline: after Save for offline use, the page was reloaded with the network switched off and both views started and tracked. This used local copies of the tracking models; saving them from Google's address is untested.
- Tap to learn (tapping a dot and tapping a label), the language switch, and a quiz round with a wrong and a right answer, in the full-body view.

Not yet tested: installing to a phone's home screen, offline use on a phone, a live camera in full-body view, a real full-length person, phones and tablets in full-body view, Safari and Firefox in full-body view, hand bones on a real hand, and graphics-card acceleration for the tracker.

Known limits of the full-body view: body tracking gives 33 points for the whole body, so the fit is looser than the head. The torso is posed as one piece, fingers and toes do not bend, and forearm rotation is not followed.

## How it is built

- `sw.js` is the offline worker, `manifest.webmanifest` and the two icons make the app installable.
- `index.html` is the whole app: the page, its code, and the anatomy meshes packed inline.
- `vendor/` holds unmodified copies of three.js 0.160.0 and MediaPipe Tasks Vision 0.10.14, so the page does not depend on a CDN. If those files are missing, the page falls back to jsDelivr.
- `src/template.html` is the page source and `src/mesh_data.js` the packed head and hand meshes. `python3 src/make.py` joins the template and data into `index.html`.
- `src/body_data.js` holds the packed body skeleton and organs, produced by `src/build_body.py` from the parts listed in `src/body_parts_used.txt`.
- `src/build_meshes.py` produced `mesh_data.js` from the BodyParts3D STL files listed in `src/parts_used.txt`. It simplifies each mesh, aligns the head to MediaPipe's canonical face model, and prepares the right hand as separate bones.

## Credits and licenses

- Anatomy models: **BodyParts3D, (c) The Database Center for Life Science (DBCLS)**, licensed under [CC BY-SA 2.1 Japan](https://creativecommons.org/licenses/by-sa/2.1/jp/deed.en). The meshes in this repository were simplified and rescaled from that dataset and are shared under the same license.
- [three.js](https://threejs.org/) is MIT licensed. [MediaPipe](https://github.com/google-ai-edge/mediapipe) is Apache 2.0 licensed.

This is an illustration for learning and fun. It is not a medical image and shows a generic anatomy model, not the person in front of the camera.
