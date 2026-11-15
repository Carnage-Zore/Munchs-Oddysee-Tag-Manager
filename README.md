# Munchs-Oddysee-Tag-Manager
A tag manager (level editor) for munches oddysee to modify or create xin/xrg files. May also be used to generate nif files for level and collision data used by the xin files.

Note this Is a WIP and may not be fully functional.

<h1> Setup </h1>

1. Download the MunchsOddyseeTagManager.zip from the releases and Import and enable the addon in blender.
2. In the N menu (the panels on the right of the 3D View Port) there will be a new Catagory: "MO Tag Manager". Open it.
3. First click Create Xin Scene. This will set up the layout of the scene hierarchy and add some collections for use.

  **Don't add things to or modify the one that says DO NOT EDIT. It is used for storing the models extracted from the nif files in the games folders and other markers that don't have a model**
  
5. There will be 4 fields to fill.

   `Game Root Folder` This is where you need to put the path to the Munches Oddysee Game folder.

   `Output Folder` This is the path where you want to output our projects to. (Later you can move them into the game folders layouts folder and point to them in the main menus levelselect.xml )

   `Region Name` The Name of the Region (the parent folder for the level folders you may add)

   `Level Name` The Name for the Level  you are editing.

After you have filled in the `Game Root Folder` and `Output Folder` you will see a new button appear: `Load All Assets`

Before you press it make sure you have the console window open or that you ran blender via the terminal if on linux.
This is not required but it will help you see whats going on when blender freezes as pressing the button will freeze blender while it
extracts the nif files from the game folder into the output folder you provided.

<h1> Adding a tag </h1>

Once everything is set up, you can start by selecting the `Markers Collection` and adding `any mesh object` into the scene.

Then with the object selected, go to the Tag Manager panel.

Set `Tag Type` to `Actor`. 

Set `Type` to any of the presets and it will immediately update the model.

An Actor is a Tag and a Tag can contain attributes and components, you can add and edit the attributes and components of an actor.

To do this, click the Show/Hide Attributes or Components buttons and then the subsequent Add/Remove Attributes or Components buttons.

Attributes Are the values on the Actor and all of them have tool tips when you hover over them to describe what they do.

Components are a generic data block that can be added to the Actor, The most obvious to understand are the Animation components.

Most of the built in actor types have their own animation component named after the type while the others either use a simple or null animation component.

The named ones have hard coded models for example the SligAnimationComponent will use a range of slig models, which you can pick from on the component itself, or using the flavor attribute in the main actor.

A `SimplAnimationComponent` as the option for a path to a file, this path is relative to the Game folders Bin folder

<h1> Geometry </h1>
As this is blender you can create the geometry yourself or import custom models to use a the geometry.
(exporting geometry may not be fully functional, but you can use it as a reference)
Make sure to select the Geometry Collection before adding the geometry you want, and don't set the Tag Type on it or your model will be replaced with a marker model.

On your geometry you can set what type of geometry it is by clicking one of the three buttons `Visual Geometry`, `Nav Geometry` and `Collision Geometry`.

You can even set it to be multiple types, generally you want the visual to also be collision, unless you want to optimize the collision by using another model, and Nav collision should be separate as it acts as an invisible wall for path finding in the game, but your able to pass through it. Its what stops characters blindly walking off edges or into mines.



