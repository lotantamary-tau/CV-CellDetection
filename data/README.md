# data/

Drop your TIF movies and tagged ROI files here. The notebook and the toolkit expect data at:

```
data/<your-movie>.tif
```

For example, the notebook references:

```python
video_path = r'../data/20250409_3_Glut_1mM_TIF_VIDEO.tif'
```

Edit that line to match your filename, or rename your file to match.

## What's gitignored here

Everything in this folder **except this README** is gitignored — TIFs, RAR archives, NPZ snapshots, anything else you drop here stays local on your machine. Each contributor supplies their own raw data; the repo stays small.

## Recommended layout

If you have multiple data types:

```
data/
├── README.md            (this file)
├── RawData/             (raw TIF videos)
└── TaggedData/          (manually segmented ROI files)
```

Both `RawData/` and `TaggedData/` will be gitignored automatically by the `data/*` rule.
