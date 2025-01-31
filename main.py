from tkinter import Tk
from labeler.app import ImageLabelerApp

def main():
    root = Tk()
    app = ImageLabelerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()