# -*- coding: utf-8 -*-
from odoo import models, api, fields, osv
import json

from odoo.exceptions import ValidationError


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'
    # fix 3 %
    tax_line_amount = fields.Float(string='tax_line_amount')
    line_amount = fields.Float(string='line_amount')
    # fix 3 %


