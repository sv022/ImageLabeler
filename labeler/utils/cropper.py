from PIL import Image, ImageTk
import os
import tkinter as Tkinter


class ImageCropper:

    def __init__(self, root):
        self.root = root
        self.root.bind("<Button-1>", self.__on_mouse_down)
        self.root.bind("<ButtonRelease-1>", self.__on_mouse_release)
        self.root.bind("<B1-Motion>", self.__on_mouse_move)
        self.root.bind("<Key>", self.__on_key_down)
        self.root.bind("<Up>", self.__on_keyUP)
        self.root.bind("<Down>", self.__on_keyDown)
        self.root.bind("<Left>", self.__on_keyLeft)
        self.root.bind("<Right>", self.__on_keyRight)
        self.message = None
        self.rectangle = None
        self.canvas_image = None
        self.canvas_message = None
        self.save_copy = True
        self.files = []
        self.box = [0, 0, 0, 0]
        self.ratio = 1.0
        self.canvas = Tkinter.Canvas(self.root, 
                             highlightthickness = 0,
                             bd = 0)

    def set_file(self, filename):
        self.files = []
        self.files.append(filename)

    def set_directory(self, directory):
        if not os.path.isdir(directory):
            raise IOError(directory + ' is not a directory')
        files = os.listdir(directory)
        if len(files) == 0:
            print( 'No files found in ' + directory)
        self.files = []
        for filename in files:
            if filename[-11:] == 'cropped.jpg':
                print( 'Ignore ' + filename)
                continue
            self.files.append(os.path.join(directory, filename))

    def roll_image(self):
        while len(self.files) > 0 and self.set_image(self.files.pop(0)) == False:
            pass

    def set_ratio(self, ratio):
        self.ratio = float(ratio)

    def check_valid_size(self):
        if self.img.size[0] < 120 and self.img.size[1] < 120:
            return False
        return True

    def set_image(self, filename):

        if filename == None:
            return True

        self.filename = filename
        self.outputname = filename[:filename.rfind('.')]
        if self.save_copy:
            self.outputname += '_cropped'
        try:
            self.img = Image.open(filename)
        except IOError:
            # print( 'Ignore: ' + filename + ' cannot be opened as an image')
            return False
        # ratio = float(self.img.size[1]) / self.img.size[0]
        if self.img.size[0] > 1200:
            self.scale = self.img.size[0] / 1200
            self.resized_img = self.img.resize( (int(self.img.size[0] / self.scale),
                                                   int(self.img.size[1] / self.scale)), )
        if self.img.size[1] > 800:
            self.scale = self.img.size[1] / 800
            self.resized_img = self.img.resize( (int(self.img.size[0] / self.scale),
                                                    int(self.img.size[1] / self.scale))
                                                    )
        if self.img.size[0] <= 1200 and self.img.size[1] <= 800:
            self.resized_img = self.img
            self.scale = 1
        self.photo = ImageTk.PhotoImage(self.resized_img)
        self.canvas.delete(self.canvas_image)
        self.canvas.config(width = self.resized_img.size[0], height = self.resized_img.size[1])
        self.canvas_image = self.canvas.create_image(0, 0, anchor = Tkinter.NW, image = self.photo)
        self.canvas.pack(fill = Tkinter.BOTH, expand = Tkinter.YES)

        self.root.update()

        return True
    
    def set_save_copy(self, save_copy : bool):
        self.save_copy = save_copy

    def __on_mouse_down(self, event):
        self.box[0], self.box[1] = event.x, event.y
        print( "top left coordinates: %s/%s" % (event.x, event.y) )
        self.canvas.delete(self.message)

    def __on_mouse_release(self, event):
        print( "bottom_right coordinates: %s/%s" % (self.box[2], self.box[3]) )
        self.box[2], self.box[3] = event.x, event.y

    def __crop_image(self):
        box = (self.box[0] * self.scale,
               self.box[1] * self.scale,
               self.box[2] * self.scale, 
               self.box[3] * self.scale)
        print(box)
        try:
            cropped = self.img.crop(box)
            if cropped.size[0] == 0 and cropped.size[1] == 0:
                raise SystemError('no size')
            cropped.save(self.outputname + '.jpg', 'jpeg')
            self.message = 'Saved: ' + self.outputname + '.jpg'
        except SystemError as e:
            print(e)

    def __fix_ratio_point(self, px, py):
        dx = px - self.box[0]
        dy = py - self.box[1]
        # if min((dy / self.ratio), dx) == dx:
        #     dy = int(dx * self.ratio)
        # else:
        #     dx = int(dy / self.ratio)
        return self.box[0] + dx, self.box[1] + dy


    def __on_mouse_move(self, event):
        self.box[2], self.box[3] = self.__fix_ratio_point(event.x, event.y)
        self.__refresh_rectangle()

    def __on_key_down(self, event):
        # print( event.char )
        if event.char == ' ':
            self.__crop_image()
            self.roll_image()
            self.canvas.delete(self.canvas_message)
            self.canvas_message = self.canvas.create_text(10, 10, anchor = Tkinter.NW, text = self.message, fill = 'red')
        elif event.char == 'q':
            self.root.destroy()

    def __on_keyUP(self, event):
        print( 'UP' )
        self.box[1] = self.box[1] - 1
        self.box[3] = self.box[3] - 1
        self.__refresh_rectangle()

    def __on_keyDown(self, event):
        self.box[1] = self.box[1] + 1
        self.box[3] = self.box[3] + 1
        self.__refresh_rectangle()
        print( 'Down' )

    def __on_keyLeft(self, event):
        print( 'Left' )
        self.box[0] = self.box[0] - 1
        self.box[2] = self.box[2] - 1
        self.__refresh_rectangle()

    def __on_keyRight(self, event):
        print( 'Right' )
        self.box[0] = self.box[0] + 1
        self.box[2] = self.box[2] + 1
        self.__refresh_rectangle()

    def __refresh_rectangle(self):
        self.canvas.delete(self.rectangle)
        self.rectangle = self.canvas.create_rectangle(self.box[0], self.box[1], self.box[2], self.box[3])

    def run(self) -> bool:
        self.roll_image()
        if not self.check_valid_size():
            self.root.destroy()
            return False
        self.root.mainloop()
        return True
