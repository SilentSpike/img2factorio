"""
Author: SilentSpike
Convert images into tiled factorio scenarios.
Requires pillow (https://python-pillow.org).
"""

import os
import argparse
import math
import colors
from shutil import copyfile
from PIL import Image, ImageOps

def maketilable(src):
    """
    Makes the image seamless
    Source: https://www.willmcgugan.com/blog/tech/post/make-tilable-backgrounds-with-python
    """
    src = src.convert("RGB")
    src_w, src_h = src.size

    dst = Image.new("RGB", (src_w, src_h))
    w, h = dst.size

    def warp(p, l, dl):
        i = float(p) / l
        i = math.sin(i*math.pi*2 + math.pi)
        i = i / 2.0 + .5
        return abs(i * dl)

    warpx = [warp(x, w-1, src_w-1) for x in range(w)]
    warpy = [warp(y, h-1, src_h-1) for y in range(h)]

    get = src.load()
    put = dst.load()

    def getpixel(x, y):

        frac_x = x - math.floor(x)
        frac_y = y - math.floor(y)

        x1 = (x+1)%src_w
        y1 = (y+1)%src_h

        a = get[x, y]
        b = get[x1, y]
        c = get[x, y1]
        d = get[x1, y1]

        area_d = frac_x * frac_y
        area_c = (1.-frac_x) * frac_y
        area_b = frac_x * (1. - frac_y)
        area_a = (1.-frac_x) * (1. - frac_y)

        a = [n*area_a for n in a]
        b = [n*area_b for n in b]
        c = [n*area_c for n in c]
        d = [n*area_d for n in d]

        return tuple(int(sum(s)) for s in zip(a,b,c,d))

    for y in range(h):
        for x in range(w):
            put[x, y] = getpixel(warpx[x], warpy[y])

    return dst

def img_to_tiles(img, tiles={0:"out-of-map"}):
    """
    Converts an image into a lua table of tile strings
    """
    w, h = img.size
    pixels = img.load()

    # Track current column so we know when to add new inner tables
    cur_x = -1

    lua_table = "{\n"
    for x in range(w):
        for y in range(h):
            # If the pixel value is associated with a tile, add to the lua table
            if pixels[x,y] in tiles:
                # New column means new inner table
                if x != cur_x:
                    # Close previous inner table before opening new
                    if cur_x != -1:
                        # Cut the last comma first
                        lua_table = lua_table.rstrip(",\n")
                        lua_table += "\n\t},\n"

                    # Open new inner table
                    lua_table += "\t[{}] = {{\n".format(x)
                    cur_x = x

                lua_table += "\t\t[{}] = \"{}\",\n".format(y, tiles[pixels[x,y]])

    # Cut the last comma and and close the table
    lua_table = lua_table.rstrip(",\n")
    lua_table += "\n\t}\n}\n"

    return lua_table

def bilevel(img, threshold=128):
    """
    Converts image to black and white by comparing pixel values to threshold
    """
    return img.convert("L").point(lambda v: 0 if v < threshold else 255, "1")

# TODO: Due to forced dithering in the quantize method this produces annoying results
# https://stackoverflow.com/questions/29433243/convert-image-to-specific-palette-using-pil-without-dithering
def rgb(img, colors):
    """
    Converts image to RGB palette in colors.py
    """
    palette = Image.new("P", (1,1))
    palette.putpalette((colors + (255,255,255) + (0,0,0)*255)[:767])

    return img.convert("RGB").quantize(palette=palette).convert("RGB")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="relative path to an image file to be converted")
    parser.add_argument("--scale", type=float, help="scale the image and maintain the aspect ratio", metavar="<coef>")
    parser.add_argument("--width", type=int, help="set the image width in pixels", metavar="<pixels>")
    parser.add_argument("--height", type=int, help="set the image height in pixels", metavar="<pixels>")
    parser.add_argument("--border", type=int, help="add a border around all edges of the image", metavar="<thickness>")
    parser.add_argument("--quantize", type=int, choices=range(1,256), help="quantize the image colours into a limited number", metavar="<number>")
    parser.add_argument("--threshold", type=int, choices=range(1,255), default=128, help="alter the greyscale value threshold pixels are compared to",  metavar="<value>")
    parser.add_argument("-c", "--color", action="store_true", help="use custom tile associations in colors.py")
    parser.add_argument("-i", "--invert", action="store_true", help="invert the image colours")
    parser.add_argument("-s", "--seamless", action="store_true", help="make the image seamless")
    parser.add_argument("-p", "--preview", action="store_true", help="save a preview image and exit")
    args = parser.parse_args()

    # Quick sanity check
    if not os.path.isfile(args.image):
        print("File doesn't exist:", args.image)
        return

    # Open the image file
    try:
        img = Image.open(args.image)
    except IOError:
        print("Failed to open:", args.image)
        return
    print("Processing:", args.image)

    # Read the width and height
    width, height = img.size
    print("Size: {}x{}px".format(width,height))

    # Resize if specified
    if args.scale or args.width or args.height:
        print("Resizing...")
        if args.scale:
            width = round(width * args.scale)
            height = round(height * args.scale)

        # Specific dimensions override scaling
        width = args.width if args.width else width
        height = args.height if args.height else height

        img = img.resize((width, height), Image.BICUBIC)
        print("New size: {}x{}px".format(width,height))

    if args.invert:
        print("Inverting...")
        img = ImageOps.invert(img)

    if args.quantize:
        print("Quantizing...")
        img = img.quantize(args.quantize)

    if args.seamless:
        print("Tiling...")
        img = maketilable(img)

    if args.border:
        print("Adding border...")
        img = ImageOps.expand(img, args.border)

    # Convert the image to limited color palette or black and white
    print("Converting colors...")
    if args.color:
        img = rgb(img, sum(colors.tiles, ()))
    else:
        img = bilevel(img, args.threshold)

    if args.preview:
        os.makedirs("preview", exist_ok=True)
        img.save(os.path.join("preview", os.path.basename(args.image)))
        print("Saved Preview")
        return # Preview mode doesnt write to lua

    # Prepare to output
    scenario = os.path.join(os.getenv("APPDATA"), "Factorio\scenarios", os.path.basename(os.path.splitext(args.image)[0]))
    control_lua = os.path.join(scenario, "control.lua")
    os.makedirs(scenario, exist_ok=True)

    # Copy the template file to the scenario folder
    try:
        copyfile("rsc\simple-tile.lua", control_lua)
    except IOError:
        print("Template failed to copy: {}".format(control_lua))
        return

    # Convert image into a lua table string
    print("Converting to lua...")
    table = img_to_tiles(img, colors.tiles if args.color else {0:colors.default})

    # Output to .lua in the respective folder
    print("Writing...")
    with open(control_lua, "a") as file:
        file.write("\nwidth = {}\nheight = {}\nimg_table = ".format(width, height))
        file.write(table)
    print("Complete")

if __name__ == "__main__":
    main()
