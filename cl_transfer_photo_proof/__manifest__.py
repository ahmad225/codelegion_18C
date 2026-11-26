# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Photo Proof on Transfers',
    'summary': 'Require a photo or PDF for every product processed before a '
               'transfer of the chosen operation types can be validated.',
    'description': """
Photo Proof on Transfers
========================
Keep picture evidence of what was received, issued or shipped. On the operation
types you choose, every product line that is processed needs at least one photo
or PDF before the transfer can be validated.

* Tick "Require Photo Proof per Product" on an operation type
  (Inventory > Configuration > Operation Types).
* In the transfer's Operations tab a camera button opens the proof files of
  the line. Take a picture with the phone camera or upload a photo or PDF; the
  Proofs column counts them and turns red while a processed line has none.
* On a phone the same files can be added from the line's detail screen.
* Validation is refused with a clear message naming the products that still
  need proof.
* When the transfer is done, one note is posted in its chatter listing each
  product with its quantity and number of files, who validated it and when,
  with the proof files attached to the note.

Behaves well:

* The rule is checked on the server when the transfer is done, so it applies
  to every way of validating: the Validate button, the backorder wizard,
  the Barcode app, imports and the API.
* Only lines that are really processed need a file. Lines left at zero for a
  backorder, and cancelled lines, never do, so partial transfers work.
* Proof files stay on the processed lines; backorder lines start without any.
* Files are stored once: the chatter note links the same files, nothing is
  copied.
* Only photos and PDF files uploaded on the line itself are accepted as
  proof: a link, an empty file, or a file that belongs to another document
  (linked by id through an import or the API) is refused.
* The proof of a done transfer cannot be changed: neither the list of files on
  the line, nor the files themselves (they cannot be deleted from the chatter
  note or replaced).
* Files follow the access rights of the transfer line: they can be opened
  only by users who can read that line (Inventory users); public users never
  see them.
* No Manufacturing Order warnings are needed: a transfer without proof simply
  cannot be validated.
* Tick the option only on operation types that people validate. Transfers of
  that type that are validated automatically (for example by another app)
  will be refused until they have proof.
* Depends only on Inventory; no Barcode or Enterprise app is required.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Inventory/Inventory',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['stock'],
    'data': [
        'views/stock_picking_type_views.xml',
        'views/stock_move_views.xml',
        'views/stock_picking_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
