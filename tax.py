# -*- coding: utf-8 -*-
from compiler.ast import obj

from odoo import models, api, fields, osv
import json

from odoo.exceptions import ValidationError


class Tax(models.Model):
    _name = 'tax.revenue'

    id_tax = fields.Char(string='เลขประจำตัวผู้เสียภาษี ', size=13)
    months = fields.Selection(
        [('01', 'มกราคม'), ('02', 'กุมภาพันธ์'), ('03', 'มีนาคม'), ('04', 'เมษายน'), ('05', 'พฤษภาคม'),
         ('06', 'มิถุนายน'), ('07', 'กรกฏาตม'), ('08', 'สิงหาคม'), ('09', 'กันยายน'), ('10', 'ตุลาคม'),
         ('11', 'พฤจิกายน'), ('12', 'ธันวาคม')], string='เดือนที่จ่ายได้พึงประเมิน')
    years = fields.Selection([('2020', '2563'), ('2021', '2564')], string='พ.ศ.')
    type_tax = fields.Selection([('sale', 'sale'), ('purchase', 'purchase')], string='การซื้อ/การขาย')
    type_amount = fields.Selection([('3', '3'), ('53', '53')], string='ภาษี ภ.ง.ด.')
    amount_total = fields.Float(string='รวมยอดเงินได้ทั้งสิ้น')
    amount_tax = fields.Float(string='รวมยอดภาษีที่นำส่งทั้งสิน')
    add_money = fields.Float(string='เงินเพิ่ม')
    amount = fields.Float(string='รวมยอดภาษีที่นำส่งทั้งสิ้น และเงินเพิ่ม(2 + 3)')
    address = fields.Char(string='ที่อยู่ของบริษัท')
    name_com = fields.Char(string='ชื่อบริษัท')
    branch = fields.Char(string='สาขา')
    ifs = fields.Selection([('S', 'หัก ณ ที่จ่าย'), ('S', 'หัก ณ ที่จ่าย')], String='Type', default='S')
    data_text = fields.Text(string='ข้อมูล')
    detail_line = fields.One2many('tax.revenue_detail', 'detail_ids', string='detail line')
    total_qty = fields.Integer("Total Qty")
    total_amount = fields.Float("Total Amount", digits=(6, 2))

    @api.multi
    def button_get_sale_order(self):
        for obj in self:
            self.amount_total = 0
            self.amount_tax = 0
            self.add_money = 0
            self.amount = 0
            obj.detail_line.unlink()
            tax = obj.id_tax
            type_tax_user = obj.type_tax
            type_amount = obj.type_amount
            month = obj.months
            # name_com = obj.name_com
            # year = str(int(obj.years) - 543)
            year = obj.years
            # import pdb; pdb.set_trace()
            tax_line_amount_query = """ UPDATE account_invoice_line ail
            SET tax_line_amount = (ail.price_subtotal * (at.amount/100))
            FROM account_invoice_line_tax ailt
            INNER JOIN account_tax at on(ailt.invoice_line_id = AT.id)
            where at.description in ('3','53')"""
            self.env.cr.execute(tax_line_amount_query)

            line_amount_query = """UPDATE account_invoice_line ail
            SET line_amount = (ail.price_subtotal + ail.tax_line_amount)
            FROM account_invoice_line_tax ailt
            INNER JOIN account_tax at on(ailt.invoice_line_id = AT.id)"""
            self.env.cr.execute(line_amount_query)

            sql = """   
                    SELECT  inv.state,
                            rp1.name AS customer_name,
                            rp1.branch_ref,
                            inv.date_invoice , 
                            inv.origin, 
                            invl.name AS product_name, 
                            invl.price_subtotal,
                            invl.tax_line_amount,
                            TO_CHAR(inv.create_date, 'yyyy') yyyy,
                            TO_CHAR(inv.create_date, 'MM') MM
                    FROM account_invoice inv 
                    INNER JOIN account_invoice_line invl on (invl.invoice_id = inv.id)
                    INNER JOIN account_invoice_line_tax lt on (lt.invoice_line_id = invl.id)
                    INNER JOIN account_tax tax on(lt.tax_id = tax.id)
                    INNER JOIN res_partner partner on (partner.id = inv.company_id)
                    INNER JOIN res_partner rp1 on (rp1.id = inv.partner_id)
                    WHERE 
                    tax.type_tax_use = '%s'
                    AND tax.description = '%s'
                    AND TO_CHAR(inv.create_date, 'yyyy') = '%s'
                    AND TO_CHAR(inv.create_date, 'MM') = '%s'
                    AND partner.vat = '%s'
                    AND inv.state = 'paid'
                    ORDER BY inv.origin
            """ % (type_tax_user, type_amount, year, month, tax)
            self.env.cr.execute(sql)
            res = self.env.cr.dictfetchall()
            for r in res:
                vals = {
                    'detail_ids': obj.id,
                    'customer_name': r['customer_name'],
                    'branch_partner': r['branch_ref'],
                    'date_invoice': r['date_invoice'],
                    'origin': r['origin'],
                    'product_name': r['product_name'],
                    'price_subtotal': r['price_subtotal'],
                    'tax_line_amount': r['tax_line_amount'],

                }

                obj.detail_line.create(vals)

                amount_untaxed = 0
                for v in self:
                    for item in v.detail_line:
                        amount_untaxed += item.price_subtotal
                self.amount_total = amount_untaxed

                amount_tax = 0
                for i in self:
                    for item in i.detail_line:
                        amount_tax += item.tax_line_amount
                self.amount_tax = amount_tax
                self.amount = amount_tax + self.add_money

    @api.onchange('add_money')
    def add_money_sum(self):
        self.amount = self.add_money + self.amount_tax

    @api.multi
    def find_taxing(self):
        if self.id_tax:
            sql = "SELECT RP.name, RP.street ,RC.x_branch  from res_partner RP " \
                  "INNER JOIN res_company RC on (RP.company_id = RC.id)" \
                  "where RP.vat in ('%s');" % self.id_tax
            self.env.cr.execute(sql)
            record_set = self.env.cr.dictfetchone()
            if record_set != None:
                self.name_com = record_set["name"]
                self.address = record_set["street"]
                self.branch = record_set["x_branch"]
            else:
                raise ValidationError('ไม่พบข้อมูล เลขประจำตัวเลขเสียภาษี')
        else:
            raise ValidationError('กรุณากรอกข้อมูล เลขประจำตัวผู้เสียภาษี')

    @api.multi
    def button_open_tax_link(self, context):
        external_web = self.env['invoice.external_web'].search([('active', '=', 1)])
        hostname = external_web.external_hostname
        prm_type = self.type_tax
        prm_desc = self.type_amount
        prm_mm = self.months
        prm_yyyy = self.years
        prm_vat = self.id_tax

        url = "%sreport/account/report_tax/rep-report-tax-service.jsp?prm_type=%s&prm_desc=%s&prm_mm=%s&" \
              "prm_yyyy=%s&prm_vat=%s" % (hostname, prm_type, prm_desc, prm_mm, prm_yyyy, prm_vat)

        return {
            'type': 'ir.actions.act_url',
            'url': '%s' % (url),
            'target': 'new',
            # 'res_id': self.id,
        }

    @api.multi
    def button_open_tax_front(self, context):
        external_web = self.env['invoice.external_web'].search([('active', '=', 1)])
        hostname = external_web.external_hostname
        id_tax = self.id_tax

        url = "%sreport/account/report_tax/rep-report-tax-service-front.jsp?prm_so=%s" \
              % (hostname, id_tax)

        return {
            'type': 'ir.actions.act_url',
            'url': '%s' % (url),
            'target': 'new',
            # 'res_id': self.id,
        }


class TaxDetail(models.Model):
    _name = 'tax.revenue_detail'
    detail_ids = fields.Many2one('tax.revenue', ondelete='set null', string='detail')
    branch_partner = fields.Char(string='สาขา')
    date_invoice = fields.Char(string='วันปีที่จ่าย')
    origin = fields.Char(string='อ้างอิง')
    price_subtotal = fields.Float(string='ราคาไม่รวมภาษี')
    customer_name = fields.Char(string='ชื่อบริษัท')
    product_name = fields.Char(string='ชื่อสินค้า')
    tax_line_amount = fields.Float(string='ภาษี')
