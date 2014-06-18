from timestream import parse
for img in parse.ts_iter_images_all_times("tests/data/timestreams/BVZ0022-GC05L-CN650D-Cam07~fullres-orig/"):
    print img
